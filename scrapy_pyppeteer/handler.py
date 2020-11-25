import asyncio
import logging
from functools import partial
from pathlib import Path
from time import time
from typing import Coroutine, Optional, Type, TypeVar

import pyppeteer
from pyppeteer.page import Page
from scrapy import Spider, signals
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.http.headers import Headers
from scrapy.responsetypes import responsetypes
from scrapy.statscollectors import StatsCollector
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred, inlineCallbacks

from ._monkeypatches import _patch_pyppeteer_connection
from .page import PageCoroutine, NavigationPageCoroutine


_patch_pyppeteer_connection()
del _patch_pyppeteer_connection


logger = logging.getLogger("scrapy-pyppeteer")


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
        self.page_coroutine_timeout: Optional[int] = None
        if crawler.settings.get("PYPPETEER_NAVIGATION_TIMEOUT"):
            self.navigation_timeout = crawler.settings.getint("PYPPETEER_NAVIGATION_TIMEOUT")
        if crawler.settings.get("PYPPETEER_PAGE_COROUTINE_TIMEOUT"):
            self.page_coroutine_timeout = crawler.settings.getint(
                "PYPPETEER_PAGE_COROUTINE_TIMEOUT"
            )
        self.browser: Optional[pyppeteer.browser.Browser] = None
        self.launch_options: dict = crawler.settings.getdict("PYPPETEER_LAUNCH_OPTIONS") or {}
        if (
            "executablePath" not in self.launch_options
            and Path(pyppeteer.executablePath()).is_file()
        ):
            self.launch_options["executablePath"] = pyppeteer.executablePath()
        logger.info("Browser launch options: %s" % self.launch_options)

    @classmethod
    def from_crawler(cls: Type[PyppeteerHandler], crawler: Crawler) -> PyppeteerHandler:
        return cls(crawler)

    def _launch_browser_signal_handler(self) -> Deferred:
        return deferred_from_coro(self._launch_browser())

    async def _launch_browser(self) -> None:
        self.browser = await pyppeteer.launch(options=self.launch_options)

    def download_request(self, request: Request, spider: Spider) -> Deferred:
        if request.meta.get("pyppeteer"):
            return deferred_from_coro(self._download_request(request, spider))
        return super().download_request(request, spider)

    async def _download_request(self, request: Request, spider: Spider) -> Response:
        try:
            page = await self.browser.newPage()  # type: ignore
            result = await self._download_request_page(request, spider, page)
        except Exception:
            if not page.isClosed():
                await page.close()
            raise
        else:
            return result

    async def _download_request_page(
        self, request: Request, spider: Spider, page: Page
    ) -> Response:
        self.stats.inc_value("pyppeteer/page_count")
        if self.navigation_timeout is not None:
            page.setDefaultNavigationTimeout(self.navigation_timeout)
        await page.setRequestInterception(True)
        page.on("request", partial(_request_handler, scrapy_request=request, stats=self.stats))
        page.on("response", partial(_response_handler, stats=self.stats))

        start_time = time()
        response = await page.goto(request.url)

        page_coroutines = request.meta.get("pyppeteer_page_coroutines") or ()
        if isinstance(page_coroutines, dict):
            page_coroutines = page_coroutines.values()
        for pc in page_coroutines:
            if isinstance(pc, PageCoroutine):
                method = getattr(page, pc.method)

                if self.page_coroutine_timeout is not None and not pc.kwargs.get("timeout", None):
                    pc.kwargs["timeout"] = self.page_coroutine_timeout

                if isinstance(pc, NavigationPageCoroutine):
                    await asyncio.gather(page.waitForNavigation(), method(*pc.args, **pc.kwargs))
                else:
                    pc.result = await method(*pc.args, **pc.kwargs)

        body = (await page.content()).encode("utf8")
        request.meta["download_latency"] = time() - start_time

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

        headers = Headers(response.headers)
        headers.pop("Content-Encoding", None)
        respcls = responsetypes.from_args(headers=headers, url=page.url, body=body)
        return respcls(
            url=page.url,
            status=response.status,
            headers=headers,
            body=body,
            request=request,
            flags=["pyppeteer"],
        )

    @inlineCallbacks
    def close(self) -> Deferred:
        yield super().close()
        if self.browser:
            yield deferred_from_coro(self.browser.close())
