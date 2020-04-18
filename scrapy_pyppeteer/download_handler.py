import asyncio
from functools import partial
from typing import Coroutine, Optional, Type, TypeVar

import pyppeteer
from scrapy import signals
from scrapy import Spider
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.responsetypes import responsetypes
from twisted.internet.defer import Deferred, inlineCallbacks

from .page import PageCoroutine, NavigationPageCoroutine


def _force_deferred(coro: Coroutine) -> Deferred:
    future = asyncio.ensure_future(coro)
    return Deferred.fromFuture(future)


async def _set_request_headers(
    request: pyppeteer.network_manager.Request, scrapy_request: Request
) -> None:
    if request.isNavigationRequest():
        headers = {
            key.decode("utf-8"): value[0].decode("utf-8")
            for key, value in scrapy_request.headers.items()
        }
        await request.continue_(overrides={"headers": headers})
    else:
        await request.continue_()


PyppeteerHandler = TypeVar("PyppeteerHandler", bound="ScrapyPyppeteerDownloadHandler")


class ScrapyPyppeteerDownloadHandler(HTTPDownloadHandler):
    def __init__(self, crawler: Crawler) -> None:
        super().__init__(settings=crawler.settings, crawler=crawler)
        self.launch_options: dict = crawler.settings.getdict("PYPPETEER_LAUNCH_OPTIONS") or {}
        self.navigation_timeout: Optional[int] = None
        if crawler.settings.get("PYPPETEER_NAVIGATION_TIMEOUT"):
            self.navigation_timeout = crawler.settings.getint("PYPPETEER_NAVIGATION_TIMEOUT")
        self.browser: Optional[pyppeteer.browser.Browser] = None
        crawler.signals.connect(self._launch_browser_signal_handler, signals.engine_started)

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
        if self.navigation_timeout is not None:
            page.setDefaultNavigationTimeout(self.navigation_timeout)
        await page.setRequestInterception(True)
        page.on("request", partial(_set_request_headers, scrapy_request=request))
        response = await page.goto(request.url)

        page_coroutines = request.meta.get("pyppeteer_page_coroutines") or ()
        for pc in page_coroutines:
            if isinstance(pc, PageCoroutine):
                method = getattr(page, pc.method)
                if isinstance(pc, NavigationPageCoroutine):
                    navigation = asyncio.ensure_future(page.waitForNavigation())
                    await asyncio.gather(navigation, method(*pc.args, **pc.kwargs))
                    result = navigation.result()
                else:
                    result = await method(*pc.args, **pc.kwargs)

            if isinstance(result, pyppeteer.network_manager.Response):
                response = result

        body = (await page.content()).encode("utf8")

        callback = request.callback or spider.parse
        annotations = getattr(callback, "__annotations__", {})
        for key, value in annotations.items():
            if value is pyppeteer.page.Page:
                request.cb_kwargs[key] = page
                break
        else:
            await page.close()

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
