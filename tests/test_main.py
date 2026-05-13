import io
import unittest
from contextlib import redirect_stdout

from matcha_bot.main import main


class MainTests(unittest.TestCase):
    def test_main_prints_greeting(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            main()

        self.assertEqual(buffer.getvalue().strip(), "Hello from matcha-bot!")


if __name__ == "__main__":
    unittest.main()
