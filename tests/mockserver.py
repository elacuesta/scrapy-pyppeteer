import re
import sys
from pathlib import Path
from subprocess import Popen, PIPE


class MockServer:
    def __enter__(self):
        self.proc = Popen(
            [sys.executable, "-u", "-m", "http.server", "0"],
            stdout=PIPE,
            cwd=Path(__file__).absolute().parent / "site",
        )
        self.address, self.port = re.search(
            r"^Serving HTTP on (\d+\.\d+\.\d+\.\d+) port (\d+)",
            self.proc.stdout.readline().strip().decode("ascii"),
        ).groups()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.communicate()
