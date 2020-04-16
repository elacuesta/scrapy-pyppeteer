import pytest
from scrapy import Spider
from scrapy.http import Request, Response
from scrapy.settings import Settings

from scrapy_pyppeteer.download_handler import ScrapyPyppeteerDownloadHandler

from tests.mockserver import MockServer


class MockSpider(Spider):
    name = "test"


@pytest.mark.asyncio
async def test_basic_response():
    handler = ScrapyPyppeteerDownloadHandler(Settings())

    with MockServer() as server:
        index = "http://{}:{}/index.html".format(server.address, server.port)
        req = Request(index)
        resp = await handler._download_request(req, MockSpider())

        assert isinstance(resp, Response)
        assert resp.request is req
        assert resp.url == index
        assert resp.status == 200

    await handler.browser.close()
