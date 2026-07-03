import asyncio
import sys
import unittest
from contextlib import asynccontextmanager
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ModuleNotFoundError:  # pragma: no cover - depends on optional extra.
    ClientSession = None


@unittest.skipIf(ClientSession is None, "install the mcp extra to run STDIO evals")
class McpStdioEvalTests(unittest.TestCase):
    def test_production_like_edit_scenarios(self) -> None:
        async def run() -> None:
            async with _session() as session:
                tools = await session.list_tools()
                self.assertEqual(
                    [tool.name for tool in tools.tools],
                    [
                        "buffer_create",
                        "buffer_list",
                        "buffer_view",
                        "buffer_edit",
                        "buffer_history",
                        "buffer_rollback",
                        "buffer_commit",
                        "command_history",
                        "command_select",
                    ],
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
                    await _call(
                        session,
                        "buffer_create",
                        {"buffer_id": buffer_id, "content": content},
                    )
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

    def test_failure_modes_are_actionable_and_atomic(self) -> None:
        async def run() -> None:
            async with _session() as session:
                await _call(session, "buffer_create", {"buffer_id": "missing", "content": "alpha"})
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
                self.assertIn("selection did not match", error)
                self.assertEqual(
                    await _call(session, "buffer_view", {"buffer_id": "missing"}),
                    before,
                )

                await _call(session, "buffer_create", {"buffer_id": "duplicate", "content": "x x"})
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
                self.assertIn("selection matched 2 targets", error)

                await _call(
                    session,
                    "buffer_create",
                    {"buffer_id": "stale", "content": "abc"},
                )
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
                self.assertIn("expected version 0", error)
                self.assertEqual(
                    (await _call(session, "buffer_view", {"buffer_id": "stale"}))["content"],
                    "abcd",
                )

                await _call(
                    session,
                    "buffer_create",
                    {
                        "buffer_id": "fuzzy",
                        "content": "install package-a\ninstall package-b",
                    },
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
                self.assertIn("fuzzy selection ambiguous", error)

                await _call(
                    session,
                    "buffer_create",
                    {"buffer_id": "blocks", "content": "``` editbuffer:id=x\na\n```\n``` editbuffer:id=x\nb\n```"},
                )
                self.assertIn(
                    "selection matched 2 targets",
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
                    ),
                )
                self.assertIn(
                    "selection did not match",
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
                    ),
                )
                self.assertIn(
                    "unknown operation",
                    await _call_error(
                        session,
                        "buffer_edit",
                        {"buffer_id": "blocks", "operation": {"op": "move"}},
                    ),
                )
                self.assertIn(
                    "unknown version",
                    await _call_error(
                        session,
                        "buffer_rollback",
                        {"buffer_id": "blocks", "version": 99},
                    ),
                )

                await _call(session, "buffer_create", {"buffer_id": "commit", "content": "done"})
                await _call(session, "buffer_commit", {"buffer_id": "commit"})
                self.assertIn(
                    "buffer is already committed",
                    await _call_error(
                        session,
                        "buffer_edit",
                        {
                            "buffer_id": "commit",
                            "operation": {"op": "append", "text": "!"},
                        },
                    ),
                )

        asyncio.run(run())


@asynccontextmanager
async def _session():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "editbuffer.mcp_server"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _call(session: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if result.isError:
        text = " ".join(getattr(block, "text", "") for block in result.content)
        raise AssertionError(f"{name} failed: {text}")
    structured = result.structuredContent
    if not isinstance(structured, dict):
        raise AssertionError(f"{name} did not return structured content")
    return structured


async def _call_error(session: Any, name: str, arguments: dict[str, Any]) -> str:
    result = await session.call_tool(name, arguments)
    if not result.isError:
        raise AssertionError(f"{name} unexpectedly succeeded: {result.structuredContent}")
    return " ".join(getattr(block, "text", "") for block in result.content)
