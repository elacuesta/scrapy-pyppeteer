def _patch_pyppeteer_connection():
    """
    Prevent Chromium from disconnecting after 20 seconds

    Taken from https://github.com/miyakogi/pyppeteer/pull/160#issuecomment-571711413
    """

    import pyppeteer
    import websockets.client

    class PatchedConnection(pyppeteer.connection.Connection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # the _ws argument is not yet connected,
            # it can be replaced by another with better defaults
            self._ws = websockets.client.connect(
                self._url, loop=self._loop, max_size=None, ping_interval=None, ping_timeout=None,
            )

    pyppeteer.connection.Connection = PatchedConnection
    pyppeteer.launcher.Connection = PatchedConnection
