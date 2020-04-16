import subprocess
from tempfile import NamedTemporaryFile

import pytest
from scrapy import Spider
from scrapy.http import Request, Response
from scrapy.settings import Settings

from scrapy_pyppeteer.download_handler import ScrapyPyppeteerDownloadHandler
from scrapy_pyppeteer.page import PageCoroutine, NavigationPageCoroutine

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


@pytest.mark.asyncio
async def test_page_coroutine_navigation():
    handler = ScrapyPyppeteerDownloadHandler(Settings())

    with MockServer() as server:
        index = "http://{}:{}/index.html".format(server.address, server.port)
        req = Request(
            index,
            meta={
                "pyppeteer_page_coroutines": [NavigationPageCoroutine("click", "a.lorem_ipsum")]
            },
        )
        resp = await handler._download_request(req, MockSpider())

    assert isinstance(resp, Response)
    assert resp.request is req
    assert resp.url == "http://{}:{}/lorem_ipsum.html".format(server.address, server.port)
    assert resp.status == 200
    assert resp.css("title::text").get() == "Lorem Ipsum"
    text = resp.css("p::text").get()
    assert text == "Lorem ipsum dolor sit amet, consectetur adipiscing elit."

    await handler.browser.close()


@pytest.mark.asyncio
async def test_page_coroutine_infinite_scroll():
    handler = ScrapyPyppeteerDownloadHandler(Settings())

    with MockServer() as server:
        index = "http://{}:{}/scroll.html".format(server.address, server.port)
        req = Request(
            index,
            meta={
                "pyppeteer_page_coroutines": [
                    PageCoroutine("waitForSelector", "div.quote"),  # first 10 quotes
                    PageCoroutine("evaluate", "window.scrollBy(0, 2000)"),
                    PageCoroutine("waitForSelector", "div.quote:nth-child(11)"),  # second request
                    PageCoroutine("evaluate", "window.scrollBy(0, 2000)"),
                    PageCoroutine("waitForSelector", "div.quote:nth-child(21)"),  # third request
                ],
            },
        )
        resp = await handler._download_request(req, MockSpider())

    assert isinstance(resp, Response)
    assert resp.request is req
    assert resp.url == "http://{}:{}/scroll.html".format(server.address, server.port)
    assert resp.status == 200
    assert len(resp.css("div.quote")) == 30

    await handler.browser.close()


@pytest.mark.asyncio
async def test_page_coroutine_screenshot_pdf():
    def get_mimetype(file):
        return subprocess.run(
            ["file", "--mime-type", "--brief", file.name],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        ).stdout.strip()

    image_file = NamedTemporaryFile()
    pdf_file = NamedTemporaryFile()
    handler = ScrapyPyppeteerDownloadHandler(Settings())

    with MockServer() as server:
        index = "http://{}:{}/index.html".format(server.address, server.port)
        req = Request(
            index,
            meta={
                "pyppeteer_page_coroutines": [
                    PageCoroutine("screenshot", options={"path": image_file.name, "type": "png"}),
                    PageCoroutine("pdf", options={"path": pdf_file.name}),
                ],
            },
        )
        await handler._download_request(req, MockSpider())
        assert get_mimetype(image_file) == "image/png"
        assert get_mimetype(pdf_file) == "application/pdf"
        image_file.close()
        pdf_file.close()

    await handler.browser.close()
