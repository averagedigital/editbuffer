import asyncio
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from editbuffer.history import ToolHistoryStore

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ModuleNotFoundError:  # pragma: no cover - depends on optional extra.
    ClientSession = None


@unittest.skipIf(ClientSession is None, "install the mcp extra to run STDIO evals")
class McpStdioEvalTests(unittest.TestCase):
    def test_production_like_edit_scenarios(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "history.sqlite3"
                async with _session(db_path) as session:
                    tools = await session.list_tools()
                    self.assertEqual(
                        {tool.name for tool in tools.tools},
                        {
                            "buffer_append",
                            "buffer_list",
                            "buffer_view",
                            "buffer_edit",
                            "buffer_replace",
                            "buffer_insert_before",
                            "buffer_insert_after",
                            "buffer_delete",
                            "buffer_history",
                            "buffer_rollback",
                            "buffer_commit",
                            "tool_history",
                            "tool_select",
                            "last_failed",
                            "select_last_failed",
                            "edit_last_failed",
                        },
                    )
                    cases = [
                        (
                            "shell",
                            'find . -name "*.py" -exec grep -n "TODO" {} ;',
                            {"type": "exact", "text": "{} ;"},
                            "{} \\;",
                            'find . -name "*.py" -exec grep -n "TODO" {} \\;',
                        ),
                        (
                            "json",
                            '{"ok": tru, "count": 1}',
                            {"type": "exact", "text": "tru"},
                            "true",
                            '{"ok": true, "count": 1}',
                        ),
                        (
                            "markdown",
                            "## Draft\n- long intro\n- action later\n",
                            {"type": "context", "before": "- ", "text": "action later", "after": "\n"},
                            "action now",
                            "## Draft\n- long intro\n- action now\n",
                        ),
                        (
                            "sql",
                            "select * from orders where status = 'paid' order created_at desc",
                            {"type": "exact", "text": "order created_at"},
                            "order by created_at",
                            "select * from orders where status = 'paid' order by created_at desc",
                        ),
                        (
                            "python",
                            "def total(items):\n    return sum(item.price for item in item)\n",
                            {"type": "exact", "text": "item)"},
                            "items)",
                            "def total(items):\n    return sum(item.price for item in items)\n",
                        ),
                        (
                            "yaml",
                            "service:\n  timeout: ten\n",
                            {"type": "exact", "text": "ten"},
                            "10",
                            "service:\n  timeout: 10\n",
                        ),
                    ]

                    for buffer_id, content, target, replacement, expected in cases:
                        await _select_seeded(session, db_path, buffer_id, content)
                        result = await _call(
                            session,
                            "buffer_edit",
                            {
                                "buffer_id": buffer_id,
                                "operation": {
                                    "op": "replace",
                                    "target": target,
                                    "text": replacement,
                                },
                            },
                        )
                        self.assertEqual(result["content"], expected)
                        self.assertEqual(result["applied"]["confidence"], 1.0)

        asyncio.run(run())

    def test_selection_edit_tools_are_first_class(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "history.sqlite3"
                async with _session(db_path) as session:
                    await _select_seeded(session, db_path, "selection-tools", "alpha beta")
                    await _call(
                        session,
                        "buffer_replace",
                        {
                            "buffer_id": "selection-tools",
                            "target": {"type": "exact", "text": "beta"},
                            "text": "gamma",
                        },
                    )
                    await _call(
                        session,
                        "buffer_insert_before",
                        {
                            "buffer_id": "selection-tools",
                            "target": {"type": "exact", "text": "gamma"},
                            "text": "new ",
                        },
                    )
                    await _call(
                        session,
                        "buffer_insert_after",
                        {
                            "buffer_id": "selection-tools",
                            "target": {"type": "exact", "text": "alpha"},
                            "text": " old",
                        },
                    )
                    await _call(
                        session,
                        "buffer_delete",
                        {
                            "buffer_id": "selection-tools",
                            "target": {"type": "exact", "text": "old "},
                        },
                    )
                    result = await _call(
                        session,
                        "buffer_append",
                        {"buffer_id": "selection-tools", "text": "!"},
                    )

                    self.assertEqual(result["content"], "alpha new gamma!")

        asyncio.run(run())

    def test_failure_modes_are_actionable_and_atomic(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "history.sqlite3"
                async with _session(db_path) as session:
                    await _select_seeded(session, db_path, "missing", "alpha")
                    before = await _call(session, "buffer_view", {"buffer_id": "missing"})
                    error = await _call_error(
                        session,
                        "buffer_edit",
                        {
                            "buffer_id": "missing",
                            "operation": {
                                "op": "replace",
                                "target": {"type": "exact", "text": "beta"},
                                "text": "gamma",
                            },
                        },
                    )
                    self.assertEqual(error["type"], "target_not_found")
                    self.assertIn("selection did not match", error["message"])
                    self.assertEqual(
                        await _call(session, "buffer_view", {"buffer_id": "missing"}),
                        before,
                    )

                    await _select_seeded(session, db_path, "duplicate", "x x")
                    error = await _call_error(
                        session,
                        "buffer_edit",
                        {
                            "buffer_id": "duplicate",
                            "operation": {
                                "op": "delete",
                                "target": {"type": "exact", "text": "x"},
                            },
                        },
                    )
                    self.assertEqual(error["type"], "ambiguous_target")
                    self.assertEqual(error["candidates"], [[0, 1], [2, 3]])

                    await _select_seeded(session, db_path, "stale", "abc")
                    await _call(
                        session,
                        "buffer_edit",
                        {"buffer_id": "stale", "operation": {"op": "append", "text": "d"}},
                    )
                    error = await _call_error(
                        session,
                        "buffer_edit",
                        {
                            "buffer_id": "stale",
                            "operation": {
                                "op": "delete",
                                "target": {
                                    "type": "range",
                                    "start": 0,
                                    "end": 1,
                                    "expected_version": 0,
                                },
                            },
                        },
                    )
                    self.assertEqual(error["type"], "stale_version")
                    self.assertEqual(error["current_version"], 1)
                    self.assertIn("expected version 0", error["message"])
                    self.assertEqual(
                        (await _call(session, "buffer_view", {"buffer_id": "stale"}))["content"],
                        "abcd",
                    )

                    await _select_seeded(
                        session,
                        db_path,
                        "fuzzy",
                        "install package-a\ninstall package-b",
                    )
                    error = await _call_error(
                        session,
                        "buffer_edit",
                        {
                            "buffer_id": "fuzzy",
                            "operation": {
                                "op": "replace",
                                "target": {
                                    "type": "fuzzy",
                                    "text": "install package-c",
                                    "threshold": 0.8,
                                    "ambiguity_margin": 0.1,
                                },
                                "text": "install package-d",
                            },
                        },
                    )
                    self.assertEqual(error["type"], "fuzzy_match")
                    self.assertEqual(error["reason"], "ambiguous")
                    self.assertGreaterEqual(len(error["candidates"]), 2)

                    await _select_seeded(
                        session,
                        db_path,
                        "blocks",
                        "``` editbuffer:id=x\na\n```\n``` editbuffer:id=x\nb\n```",
                    )
                    self.assertEqual(
                        (
                            await _call_error(
                                session,
                                "buffer_edit",
                                {
                                    "buffer_id": "blocks",
                                    "operation": {
                                        "op": "delete",
                                        "target": {"type": "block", "block_id": "x"},
                                    },
                                },
                            )
                        )["type"],
                        "ambiguous_target",
                    )
                    self.assertEqual(
                        (
                            await _call_error(
                                session,
                                "buffer_edit",
                                {
                                    "buffer_id": "blocks",
                                    "operation": {
                                        "op": "delete",
                                        "target": {"type": "block", "block_id": "missing"},
                                    },
                                },
                            )
                        )["type"],
                        "target_not_found",
                    )
                    self.assertEqual(
                        (
                            await _call_error(
                                session,
                                "buffer_edit",
                                {"buffer_id": "blocks", "operation": {"op": "move"}},
                            )
                        )["type"],
                        "invalid_operation",
                    )
                    self.assertEqual(
                        (
                            await _call_error(
                                session,
                                "buffer_rollback",
                                {"buffer_id": "blocks", "version": 99},
                            )
                        )["type"],
                        "invalid_operation",
                    )

                    await _select_seeded(session, db_path, "commit", "done")
                    await _call(session, "buffer_commit", {"buffer_id": "commit"})
                    error = await _call_error(
                        session,
                        "buffer_edit",
                        {
                            "buffer_id": "commit",
                            "operation": {"op": "append", "text": "!"},
                        },
                    )
                    self.assertEqual(error["type"], "invalid_operation")
                    self.assertIn("buffer is already committed", error["message"])

        asyncio.run(run())


@asynccontextmanager
async def _session(db_path: Path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "editbuffer.mcp_server"],
        env={"EDITBUFFER_HISTORY_DB": str(db_path)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _select_seeded(
    session: Any,
    db_path: Path,
    buffer_id: str,
    content: str,
) -> dict[str, Any]:
    call_id = f"seed-{buffer_id}"
    ToolHistoryStore(db_path).record_tool_call(
        "seed",
        {"content": content},
        call_id=call_id,
        result={"content": content},
        content=content,
    )
    return await _call(session, "tool_select", {"call_id": call_id, "buffer_id": buffer_id})


async def _call(session: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if result.isError:
        text = " ".join(getattr(block, "text", "") for block in result.content)
        raise AssertionError(f"{name} failed: {text}")
    structured = result.structuredContent
    if not isinstance(structured, dict):
        raise AssertionError(f"{name} did not return structured content")
    return structured


async def _call_error(session: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if result.isError:
        text = " ".join(getattr(block, "text", "") for block in result.content)
        raise AssertionError(f"{name} returned unstructured MCP error: {text}")
    structured = result.structuredContent
    if not isinstance(structured, dict) or structured.get("ok") is not False:
        raise AssertionError(f"{name} unexpectedly succeeded: {structured}")
    error = structured.get("error")
    if not isinstance(error, dict):
        raise AssertionError(f"{name} did not return a structured error: {structured}")
    return error
