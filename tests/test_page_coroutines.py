import pytest

from scrapy_pyppeteer.page import PageCoroutine, NavigationPageCoroutine


@pytest.mark.asyncio
async def test_page_coroutines():
    screenshot = PageCoroutine("screenshot", options={"path": "/tmp/file", "type": "png"})
    assert screenshot.method == "screenshot"
    assert screenshot.args == ()
    assert screenshot.kwargs == {"options": {"path": "/tmp/file", "type": "png"}}
    assert screenshot.result is None
    assert str(screenshot) == "<PageCoroutine for method 'screenshot'>"

    click = NavigationPageCoroutine("click", "div a.link")
    assert click.method == "click"
    assert click.args == ("div a.link",)
    assert click.kwargs == {}
    assert click.result is None
    assert str(click) == "<NavigationPageCoroutine for method 'click'>"
