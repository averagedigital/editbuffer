import unittest
from datetime import UTC, datetime, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path

from editbuffer.mcp_server import BufferRegistry
from editbuffer.history import ToolHistoryStore


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
        with TemporaryDirectory() as tmp:
            store = ToolHistoryStore(Path(tmp) / "history.sqlite3")
            registry = BufferRegistry(history_store=store)
            registry.create("pytest tests/test_mcp_server.py", buffer_id="cmd")

            registry.commit("cmd")
            selected = registry.select_command("cmd-1", buffer_id="reuse")

            self.assertEqual(registry.command_history()[0]["command"], "pytest tests/test_mcp_server.py")
            self.assertEqual(selected["content"], "pytest tests/test_mcp_server.py")
            self.assertEqual(selected["buffer_id"], "reuse")
            self.assertFalse(selected["committed"])

    def test_command_history_keeps_last_10_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            registry = BufferRegistry(history_store=ToolHistoryStore(Path(tmp) / "history.sqlite3"))

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

    def test_command_select_uses_sqlite_history(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "history.sqlite3"
            registry = BufferRegistry(history_store=ToolHistoryStore(db_path))
            registry.create("pytest -q", buffer_id="cmd")
            registry.commit("cmd")

            fresh_registry = BufferRegistry(history_store=ToolHistoryStore(db_path))
            selected = fresh_registry.select_command("cmd-1", buffer_id="reuse")

            self.assertEqual(selected["content"], "pytest -q")
            self.assertEqual(selected["buffer_id"], "reuse")

    def test_sqlite_tool_history_persists_and_redacts_secret_like_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "history.sqlite3"
            store = ToolHistoryStore(db_path)
            call_id = store.record_tool_call(
                "buffer_create",
                {"content": "x", "api_key": "sk-secret", "nested": {"token": "abc"}},
                result={"buffer_id": "x", "content": "x"},
            )

            persisted = ToolHistoryStore(db_path).list_tool_calls()

            self.assertEqual(persisted[0]["call_id"], call_id)
            self.assertEqual(persisted[0]["arguments"]["api_key"], "[REDACTED]")
            self.assertEqual(persisted[0]["arguments"]["nested"]["token"], "[REDACTED]")
            self.assertEqual(persisted[0]["status"], "success")

    def test_tool_history_retention_and_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            store = ToolHistoryStore(Path(tmp) / "history.sqlite3", retention_days=7, default_limit=10)
            old = datetime.now(UTC) - timedelta(days=8)
            store.record_tool_call("buffer_view", {"buffer_id": "old"}, timestamp=old)
            for number in range(12):
                store.record_tool_call("buffer_view", {"buffer_id": str(number)})

            history = store.list_tool_calls()

            self.assertEqual(len(history), 10)
            self.assertEqual(history[0]["arguments"]["buffer_id"], "11")
            self.assertNotIn("old", {item["arguments"]["buffer_id"] for item in history})

    def test_tool_select_can_create_buffer_from_sqlite_history(self) -> None:
        with TemporaryDirectory() as tmp:
            registry = BufferRegistry(history_store=ToolHistoryStore(Path(tmp) / "history.sqlite3"))
            call_id = registry.record_tool_call(
                "shell",
                {"command": "pytest tests/test_mcp_server.py"},
                status="failed",
                error="exit 1",
            )

            selected = registry.select_tool_call(call_id, buffer_id="repair")

            self.assertEqual(selected["content"], "pytest tests/test_mcp_server.py")
            self.assertEqual(selected["buffer_id"], "repair")

    def test_missing_tool_call_selection_fails_explicitly(self) -> None:
        with TemporaryDirectory() as tmp:
            registry = BufferRegistry(history_store=ToolHistoryStore(Path(tmp) / "history.sqlite3"))

            with self.assertRaises(KeyError):
                registry.select_tool_call("missing")


if __name__ == "__main__":
    unittest.main()
