# Pyppeteeer integration for Scrapy

This project provides a Scrapy Download Handler which performs requests using
[Pyppeteeer](https://github.com/miyakogi/pyppeteer). It can be used to handle
pages that require JavaScript.


## Motivation

After the release of [version 2.0](https://docs.scrapy.org/en/latest/news.html#scrapy-2-0-0-2020-03-03),
which includes partial [coroutine syntax support](https://docs.scrapy.org/en/2.0/topics/coroutines.html)
and experimental [asyncio support](https://docs.scrapy.org/en/2.0/topics/asyncio.html), Scrapy allows
to integrate `asyncio`-based projects such as `Pyppeteeer`.


## Installation

This package is not (yet) available on PyPI, but it can be installed from GitHub:
```
$ pip install https://github.com/elacuesta/scrapy-pyppeteer
```

## Configuration

Replace the default `http` and `https` Download Handlers through the
[`DOWNLOAD_HANDLERS`](https://docs.scrapy.org/en/latest/topics/settings.html):

```python
DOWNLOAD_HANDLERS = {
    "http": "scrapy_pyppeteer.ScrapyPyppeteerDownloadHandler",
    "https": "scrapy_pyppeteer.ScrapyPyppeteerDownloadHandler",
}
```

Note that the `ScrapyPyppeteerDownloadHandler` class inherits from the default
`http/https` handler, and it will only use Pyppeteeer for requests that are
explicitly marked (see the "Basic usage" section for details).

Also, be sure to [install the `asyncio`-based Twisted reactor](https://docs.scrapy.org/en/latest/topics/asyncio.html#installing-the-asyncio-reactor):

```python
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
```

`scrapy-pyppeteer` accepts the following settings:

* `PYPPETEER_LAUNCH_OPTIONS` (type `dict`, default `{}`)

    A dictionary with options to be passed when launching the Browser.
    See the docs for [pyppeteer.launcher.launch](https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.launcher.launch)

* `PYPPETEER_NAVIGATION_TIMEOUT` (type `Optional[int]`, default `None`)

    The timeout used when requesting pages by Pyppeteer. If `None` or unset,
    the default value will be used (30000 ms at the time of writing this).
    See the docs for [pyppeteer.page.Page.setDefaultNavigationTimeout](https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.setDefaultNavigationTimeout)


## Basic usage

Set the `pyppeteer_enable` [Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta)
key to download a request using Pyppeteer:

```python
import scrapy

class AwesomeSpider(scrapy.Spider):
    def start_requests(self):
        yield scrapy.Request("https://example.org", meta={"pyppeteer_enable": True})

    def parse(self, response):
        yield scrapy.Request("https://scrapy.org", meta={"pyppeteer_enable": True)
```


## Page coroutines

WIP


## Examples

WIP


## Acknowledgements

This project was inspired by:

* https://github.com/scrapy/scrapy/pull/1455
* https://github.com/michalmo/scrapy-browser
* https://github.com/lopuhin/scrapy-pyppeteer
* https://github.com/clemfromspace/scrapy-puppeteer
