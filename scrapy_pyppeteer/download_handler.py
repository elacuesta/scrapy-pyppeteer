import asyncio
import logging
from functools import partial
from typing import Coroutine, Optional, Type, TypeVar

import pyppeteer
from scrapy import Spider, signals
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.responsetypes import responsetypes
from scrapy.statscollectors import StatsCollector
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred, inlineCallbacks

from .page import PageCoroutine, NavigationPageCoroutine


logger = logging.getLogger("scrapy-pyppeteer")


def _force_deferred(coro: Coroutine) -> Deferred:
    future = asyncio.ensure_future(coro)
    return Deferred.fromFuture(future)


async def _request_handler(
    request: pyppeteer.network_manager.Request, scrapy_request: Request, stats: StatsCollector
) -> None:
    # set headers, method and body
    if request.url == scrapy_request.url:
        overrides = {
            "method": scrapy_request.method,
            "headers": {
                key.decode("utf-8"): value[0].decode("utf-8")
                for key, value in scrapy_request.headers.items()
            },
        }
        if scrapy_request.body:
            overrides["postData"] = scrapy_request.body.decode(scrapy_request.encoding)
        await request.continue_(overrides)
    else:
        await request.continue_()
    # increment stats
    stats.inc_value("pyppeteer/request_method_count/{}".format(request.method))
    stats.inc_value("pyppeteer/request_count")
    if request.isNavigationRequest():
        stats.inc_value("pyppeteer/request_count/navigation")


async def _response_handler(response: pyppeteer.network_manager.Response, stats: StatsCollector):
    stats.inc_value("pyppeteer/response_count")
    stats.inc_value("pyppeteer/response_status_count/{}".format(response.status))


PyppeteerHandler = TypeVar("PyppeteerHandler", bound="ScrapyPyppeteerDownloadHandler")


class ScrapyPyppeteerDownloadHandler(HTTPDownloadHandler):
    def __init__(self, crawler: Crawler) -> None:
        super().__init__(settings=crawler.settings, crawler=crawler)
        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        crawler.signals.connect(self._launch_browser_signal_handler, signals.engine_started)
        self.stats = crawler.stats
        self.navigation_timeout: Optional[int] = None
        if crawler.settings.get("PYPPETEER_NAVIGATION_TIMEOUT"):
            self.navigation_timeout = crawler.settings.getint("PYPPETEER_NAVIGATION_TIMEOUT")
        self.browser: Optional[pyppeteer.browser.Browser] = None
        self.launch_options: dict = crawler.settings.getdict("PYPPETEER_LAUNCH_OPTIONS") or {}
        logger.info("Browser launch options: %s" % self.launch_options)

    @classmethod
    def from_crawler(cls: Type[PyppeteerHandler], crawler: Crawler) -> PyppeteerHandler:
        return cls(crawler)

    def _launch_browser_signal_handler(self) -> Deferred:
        return _force_deferred(self._launch_browser())

    async def _launch_browser(self) -> None:
        self.browser = await pyppeteer.launch(options=self.launch_options)

    def download_request(self, request: Request, spider: Spider) -> Deferred:
        if request.meta.get("pyppeteer"):
            return _force_deferred(self._download_request(request, spider))
        return super().download_request(request, spider)

    async def _download_request(self, request: Request, spider: Spider) -> Response:
        page = await self.browser.newPage()  # type: ignore
        self.stats.inc_value("pyppeteer/page_count")
        if self.navigation_timeout is not None:
            page.setDefaultNavigationTimeout(self.navigation_timeout)
        await page.setRequestInterception(True)
        page.on("request", partial(_request_handler, scrapy_request=request, stats=self.stats))
        page.on("response", partial(_response_handler, stats=self.stats))
        response = await page.goto(request.url)

        page_coroutines = request.meta.get("pyppeteer_page_coroutines") or ()
        for pc in page_coroutines:
            if isinstance(pc, PageCoroutine):
                method = getattr(page, pc.method)
                if isinstance(pc, NavigationPageCoroutine):
                    await asyncio.gather(page.waitForNavigation(), method(*pc.args, **pc.kwargs))
                else:
                    await method(*pc.args, **pc.kwargs)

        body = (await page.content()).encode("utf8")

        callback = request.callback or spider.parse
        annotations = getattr(callback, "__annotations__", {})
        for key, value in annotations.items():
            if value is pyppeteer.page.Page:
                request.cb_kwargs[key] = page
                self.stats.inc_value("pyppeteer/page_count/injected_callback")
                break
        else:
            await page.close()
            self.stats.inc_value("pyppeteer/page_count/closed")

        response.headers.pop("content-encoding", None)
        respcls = responsetypes.from_args(headers=response.headers, url=response.url, body=body)
        return respcls(
            url=page.url,
            status=response.status,
            headers=response.headers,
            body=body,
            request=request,
            flags=["pyppeteer"],
        )

    @inlineCallbacks
    def close(self) -> Deferred:
        yield super().close()
        if self.browser:
            yield _force_deferred(self.browser.close())
