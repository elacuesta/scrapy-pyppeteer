from scrapy import Spider
from scrapy.http import Request, Response
from scrapy.settings import Settings
from twisted.internet import defer
from twisted.trial.unittest import TestCase

from scrapy_pyppeteer.download_handler import ScrapyPyppeteerDownloadHandler
from tests.mockserver import MockServer


class MixedRequestsTestCase(TestCase):
    def setUp(self):
        self.server = MockServer()
        self.server.__enter__()
        self.base_url = "http://{}:{}".format(self.server.address, self.server.port)
        self.handler = ScrapyPyppeteerDownloadHandler(Settings())

    @defer.inlineCallbacks
    def tearDown(self):
        self.server.__exit__(None, None, None)
        yield self.handler.close()

    def test_regular_request(self):
        def _test(response):
            self.assertIsInstance(response, Response)
            self.assertEqual(response.css("a::text").getall(), ["Lorem Ipsum", "Infinite Scroll"])
            self.assertEqual(response.url, request.url)
            self.assertEqual(response.status, 200)
            self.assertNotIn("pyppeteer", response.flags)

        request = Request(self.base_url + "/index.html")
        return self.handler.download_request(request, Spider("foo")).addCallback(_test)

    def test_pyppeteer_request(self):
        def _test(response):
            self.assertIsInstance(response, Response)
            self.assertEqual(response.css("a::text").getall(), ["Lorem Ipsum", "Infinite Scroll"])
            self.assertEqual(response.url, request.url)
            self.assertEqual(response.status, 200)
            self.assertIn("pyppeteer", response.flags)

        request = Request(self.base_url + "/index.html", meta={"pyppeteer": True})
        return self.handler.download_request(request, Spider("foo")).addCallback(_test)
