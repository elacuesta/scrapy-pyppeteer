import asyncio
from contextlib import suppress
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


def _force_deferred(coro: Coroutine) -> Deferred:
    dfd = Deferred().addCallback(lambda f: f.result())
    future = asyncio.ensure_future(coro)
    future.add_done_callback(dfd.callback)
    return dfd


async def _set_request_headers(
    request: pyppeteer.network_manager.Request, scrapy_request: Request
) -> None:
    headers = {
        key.decode("utf-8"): value[0].decode("utf-8")
        for key, value in scrapy_request.headers.items()
    }
    await request.continue_(overrides={"headers": headers})


class PageAction:
    """
    Represents an action to be executed on a page,
    such as "click", "screenshot" or "hover"
    """

    def __init__(self, method: str, *args, **kwargs) -> None:
        self.method = method
        self.args = args
        self.kwargs = kwargs


class NavigationPageAction(PageAction):
    """
    Same as PageAction, but it waits for a navigation event
    (forces a Page.waitForNavigation() call wrapped in asyncio.gather)

    See https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.waitForNavigation
    """
    pass


class ScrapyPyppeteerDownloadHandler(HTTPDownloadHandler):
    def __init__(self, settings: Settings, crawler: Optional[Crawler] = None) -> None:
        super().__init__(settings=settings, crawler=crawler)
        self.browser: Optional[pyppeteer.browser.Browser] = None

    def download_request(self, request: Request, spider: Spider):
        with suppress(KeyError):
            if request.meta["pyppeteer"]["enable"]:
                return _force_deferred(self._download_request(request, spider))
        return super().download_request(request, spider)

    async def _download_request(self, request: Request, spider: Spider) -> Response:
        if self.browser is None:
            self.browser = await pyppeteer.launch()

        page = await self.browser.newPage()
        await page.setRequestInterception(True)
        page.on("request", partial(_set_request_headers, scrapy_request=request))
        response = await page.goto(request.url)

        page_actions = request.meta["pyppeteer"].get("page_actions") or []
        for action in page_actions:
            method = getattr(page, action.method)
            if isinstance(action, NavigationPageAction):
                result = await asyncio.gather(
                    page.waitForNavigation(), method(*action.args, **action.kwargs),
                )
                result = next(filter(None, result))
            elif isinstance(action, PageAction):
                result = await method(*action.args, **action.kwargs)
            if isinstance(result, pyppeteer.network_manager.Response):
                response = result

        body = (await response.text()).encode("utf8")
        await page.close()
        respcls = responsetypes.from_args(headers=response.headers, url=response.url, body=body)
        return respcls(
            url=response.url,
            status=response.status,
            headers=response.headers,
            body=body,
            request=request,
        )
