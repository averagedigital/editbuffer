import unittest

from editbuffer.mcp_server import BufferRegistry


class BufferRegistryTests(unittest.TestCase):
    def test_complete_mcp_workflow(self) -> None:
        registry = BufferRegistry()

        created = registry.create("hello world", buffer_id="answer")
        edited = registry.edit(
            "answer",
            {
                "op": "replace",
                "target": {"type": "exact", "text": "world"},
                "text": "there",
            },
        )
        rolled_back = registry.rollback("answer", 0)
        committed = registry.commit("answer")

        self.assertEqual(created["buffer_id"], "answer")
        self.assertEqual(edited["content"], "hello there")
        self.assertEqual(edited["applied"]["confidence"], 1.0)
        self.assertEqual(rolled_back["content"], "hello world")
        self.assertEqual(committed["content"], "hello world")
        self.assertTrue(committed["committed"])

    def test_registry_history_is_serializable(self) -> None:
        registry = BufferRegistry()
        registry.create("a", buffer_id="x")
        registry.edit("x", {"op": "append", "text": "b"})

        history = registry.history("x")

        self.assertEqual(history[0]["operation"]["op"], "append")
        self.assertEqual(history[0]["version_after"], 1)

    def test_duplicate_and_missing_buffers_fail_explicitly(self) -> None:
        registry = BufferRegistry()
        registry.create(buffer_id="x")

        with self.assertRaises(ValueError):
            registry.create(buffer_id="x")
        with self.assertRaises(KeyError):
            registry.view("missing")

    def test_committed_commands_are_kept_for_reuse(self) -> None:
        registry = BufferRegistry()
        registry.create("pytest tests/test_mcp_server.py", buffer_id="cmd")

        registry.commit("cmd")
        selected = registry.select_command("cmd-1", buffer_id="reuse")

        self.assertEqual(registry.command_history()[0]["command"], "pytest tests/test_mcp_server.py")
        self.assertEqual(selected["content"], "pytest tests/test_mcp_server.py")
        self.assertEqual(selected["buffer_id"], "reuse")
        self.assertFalse(selected["committed"])

    def test_command_history_keeps_last_10_commands(self) -> None:
        registry = BufferRegistry()

        for number in range(12):
            registry.create(f"cmd {number}", buffer_id=f"cmd-{number}")
            registry.commit(f"cmd-{number}")

        history = registry.command_history()

        self.assertEqual(len(history), 10)
        self.assertEqual(history[0]["command"], "cmd 11")
        self.assertEqual(history[-1]["command"], "cmd 2")

    def test_unknown_command_selection_fails_explicitly(self) -> None:
        registry = BufferRegistry()

        with self.assertRaises(KeyError):
            registry.select_command("missing")


if __name__ == "__main__":
    unittest.main()
