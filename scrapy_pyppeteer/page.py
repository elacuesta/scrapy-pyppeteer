class PageCoroutine:
    """
    Represents a coroutine to be awaited on a Pyppeteer page,
    such as "click", "screenshot" or "evaluate"
    """

    def __init__(self, method: str, *args, **kwargs) -> None:
        self.method = method
        self.args = args
        self.kwargs = kwargs


class NavigationPageCoroutine(PageCoroutine):
    """
    Same as PageCoroutine, but it waits for a navigation event. Use this when you know
    a coroutine will trigger a navigation event, for instance when clicking on a link.

    This forces a Page.waitForNavigation() call wrapped in asyncio.gather, as recommended in
    https://miyakogi.github.io/pyppeteer/reference.html#pyppeteer.page.Page.click
    """

    pass
