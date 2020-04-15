import asyncio
from functools import partial
from typing import Coroutine, Optional

import pyppeteer
from scrapy import Spider
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.responsetypes import responsetypes
from scrapy.settings import Settings
from twisted.internet.defer import Deferred

from .actions import PageAction, NavigationPageAction


def _force_deferred(coro: Coroutine) -> Deferred:
    dfd = Deferred().addCallback(lambda f: f.result())
    future = asyncio.ensure_future(coro)
    future.add_done_callback(dfd.callback)
    return dfd


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


class ScrapyPyppeteerDownloadHandler(HTTPDownloadHandler):
    def __init__(self, settings: Settings, crawler: Optional[Crawler] = None) -> None:
        super().__init__(settings=settings, crawler=crawler)
        self.browser = None
        self.launch_options = settings.getdict("PYPPETEER_LAUNCH_OPTIONS") or {}
        self.navigation_timeout = None
        if settings.get("PYPPETEER_NAVIGATION_TIMEOUT"):
            self.navigation_timeout = settings.getint("PYPPETEER_NAVIGATION_TIMEOUT")

    def download_request(self, request: Request, spider: Spider):
        if request.meta.get("pyppeteer_enable"):
            return _force_deferred(self._download_request(request, spider))
        return super().download_request(request, spider)

    async def _download_request(self, request: Request, spider: Spider) -> Response:
        if self.browser is None:
            self.browser = await pyppeteer.launch(options=self.launch_options)

        page = await self.browser.newPage()  # type: ignore
        if self.navigation_timeout is not None:
            page.setDefaultNavigationTimeout(self.navigation_timeout)
        await page.setRequestInterception(True)
        page.on("request", partial(_set_request_headers, scrapy_request=request))
        response = await page.goto(request.url)

        page_actions = request.meta.get("pyppeteer_page_actions") or []
        for action in page_actions:
            if isinstance(action, PageAction):
                method = getattr(page, action.method)
                if isinstance(action, NavigationPageAction):
                    navigation = asyncio.ensure_future(page.waitForNavigation())
                    await asyncio.gather(navigation, method(*action.args, **action.kwargs))
                    result = navigation.result()
                else:
                    result = await method(*action.args, **action.kwargs)
            elif asyncio.iscoroutine(action):
                result = await action

            if isinstance(result, pyppeteer.network_manager.Response):
                response = result

        body = (await page.content()).encode("utf8")
        await page.close()
        respcls = responsetypes.from_args(headers=response.headers, url=response.url, body=body)
        return respcls(
            url=page.url,
            status=response.status,
            headers=response.headers,
            body=body,
            request=request,
        )
