import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from editbuffer.cli import main


class CliTests(unittest.TestCase):
    def test_state_file_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = str(Path(directory) / "buffer.json")

            self.assertEqual(main(["new", state, "--text", "hello world"]), 0)
            self.assertEqual(
                main(
                    [
                        "replace",
                        state,
                        '{"type":"exact","text":"world"}',
                        "there",
                    ]
                ),
                0,
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["commit", state]), 0)

            self.assertEqual(output.getvalue(), "hello there\n")


if __name__ == "__main__":
    unittest.main()
