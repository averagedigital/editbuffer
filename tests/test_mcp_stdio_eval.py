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
    def test_mcp_exposes_minimal_command_repair_surface(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "history.sqlite3"
                async with _session(db_path) as session:
                    tools = await session.list_tools()
                    self.assertEqual(
                        {tool.name for tool in tools.tools},
                        {"repair_failed_command"},
                    )
                    schema = tools.tools[0].inputSchema
                    self.assertEqual(set(schema["required"]), {"old_text", "new_text"})
                    self.assertIn("call_id", schema["properties"])

        asyncio.run(run())

    def test_repair_last_failed_returns_command_without_executing(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "history.sqlite3"
                output = Path(tmp) / "repaired.txt"
                ToolHistoryStore(db_path).record_tool_call(
                    "exec_command",
                    {"cmd": f"printf broken > {output}"},
                    tool_kind="shell",
                    cwd=str(Path.cwd()),
                    status="failed",
                    error="No such file or directory",
                )
                async with _session(db_path) as session:
                    result = await _call(
                        session,
                        "repair_failed_command",
                        {"old_text": "broken", "new_text": "repaired"},
                    )

                    self.assertEqual(
                        result["repaired_command"], f"printf repaired > {output}"
                    )
                    self.assertFalse(output.exists())

        asyncio.run(run())

    def test_ambiguous_repair_returns_actionable_error(self) -> None:
        async def run() -> None:
            with TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "history.sqlite3"
                ToolHistoryStore(db_path).record_tool_call(
                    "exec_command",
                    {"cmd": "echo old old"},
                    tool_kind="shell",
                    cwd=str(Path.cwd()),
                    status="failed",
                )
                async with _session(db_path) as session:
                    error = await _call_error(
                        session,
                        "repair_failed_command",
                        {"old_text": "old", "new_text": "new"},
                    )

                    self.assertEqual(error["type"], "ambiguous_target")
                    self.assertEqual(error["candidates"], [[5, 8], [9, 12]])

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


async def _call(session: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if result.isError:
        text = " ".join(getattr(block, "text", "") for block in result.content)
        raise AssertionError(f"{name} failed: {text}")
    structured = result.structuredContent
    if not isinstance(structured, dict):
        raise AssertionError(f"{name} did not return structured content")
    return structured


async def _call_error(
    session: Any, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
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
