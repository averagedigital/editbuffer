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


if __name__ == "__main__":
    unittest.main()
