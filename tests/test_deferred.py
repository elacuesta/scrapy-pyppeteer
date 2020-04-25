import asyncio
from twisted.trial.unittest import TestCase

from scrapy_pyppeteer.handler import _force_deferred


class ForceDeferredTestCase(TestCase):
    def test_coroutine_to_deferred(self):
        def _test(result):
            self.assertIsInstance(result, str)
            self.assertEqual(result, "Hello!")

        async def say_hello():
            await asyncio.sleep(0.01)
            return "Hello!"

        dfd = _force_deferred(say_hello())
        dfd.addCallback(_test)
        return dfd
