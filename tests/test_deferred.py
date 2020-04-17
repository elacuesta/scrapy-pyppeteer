import os
import shutil

from scrapy import Spider
from scrapy.http import Request
from scrapy.settings import Settings
from scrapy.utils.python import to_bytes
from twisted.internet import defer, reactor
from twisted.protocols.policies import WrappingFactory
from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase
from twisted.web import server, static, util
from twisted.web.test.test_webclient import HostHeaderResource, PayloadResource

from scrapy_pyppeteer.download_handler import ScrapyPyppeteerDownloadHandler


class HttpTestCase(TestCase):
    def setUp(self):
        self.tmpname = self.mktemp()
        os.mkdir(self.tmpname)
        FilePath(self.tmpname).child("file").setContent(b"0123456789")
        r = static.File(self.tmpname)
        r.putChild(b"redirect", util.Redirect(b"/file"))
        r.putChild(b"host", HostHeaderResource())
        r.putChild(b"payload", PayloadResource())
        self.site = server.Site(r, timeout=None)
        self.wrapper = WrappingFactory(self.site)
        self.host = "localhost"
        self.port = reactor.listenTCP(0, self.wrapper, interface=self.host)
        self.portno = self.port.getHost().port
        self.download_handler = ScrapyPyppeteerDownloadHandler(Settings())
        self.download_request = self.download_handler.download_request

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.port.stopListening()
        if hasattr(self.download_handler, "close"):
            yield self.download_handler.close()
        shutil.rmtree(self.tmpname)

    def getURL(self, path):
        return "http://%s:%d/%s" % (self.host, self.portno, path)

    def test_download(self):
        request = Request(self.getURL("file"))
        d = self.download_request(request, Spider("foo"))
        d.addCallback(lambda r: r.body)
        d.addCallback(self.assertEqual, b"0123456789")
        return d

    def test_download_head(self):
        request = Request(self.getURL("file"), method="HEAD")
        d = self.download_request(request, Spider("foo"))
        d.addCallback(lambda r: r.body)
        d.addCallback(self.assertEqual, b"")
        return d

    def test_redirect_status(self):
        request = Request(self.getURL("redirect"))
        d = self.download_request(request, Spider("foo"))
        d.addCallback(lambda r: r.status)
        d.addCallback(self.assertEqual, 302)
        return d

    def test_redirect_status_head(self):
        request = Request(self.getURL("redirect"), method="HEAD")
        d = self.download_request(request, Spider("foo"))
        d.addCallback(lambda r: r.status)
        d.addCallback(self.assertEqual, 302)
        return d

    def test_host_header_not_in_request_headers(self):
        def _test(response):
            self.assertEqual(response.body, to_bytes("%s:%d" % (self.host, self.portno)))
            self.assertEqual(request.headers, {})

        request = Request(self.getURL("host"))
        return self.download_request(request, Spider("foo")).addCallback(_test)

    def test_host_header_seted_in_request_headers(self):
        def _test(response):
            self.assertEqual(response.body, b"example.com")
            self.assertEqual(request.headers.get("Host"), b"example.com")

        request = Request(self.getURL("host"), headers={"Host": "example.com"})
        return self.download_request(request, Spider("foo")).addCallback(_test)

        d = self.download_request(request, Spider("foo"))
        d.addCallback(lambda r: r.body)
        d.addCallback(self.assertEqual, b"example.com")
        return d

    def test_payload(self):
        body = b"1" * 100  # PayloadResource requires body length to be 100
        request = Request(self.getURL("payload"), method="POST", body=body)
        d = self.download_request(request, Spider("foo"))
        d.addCallback(lambda r: r.body)
        d.addCallback(self.assertEqual, body)
        return d
