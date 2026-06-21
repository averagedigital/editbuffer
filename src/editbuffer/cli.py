from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .buffer import EditBuffer
from .errors import EditBufferError, InvalidOperationError


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    state_path = Path(args.state)

    try:
        if args.command == "new":
            if state_path.exists():
                raise InvalidOperationError(f"state already exists: {state_path}")
            _save(state_path, {"initial": args.text, "operations": [], "committed": False})
            return 0

        state = _load(state_path)
        buffer = _restore(state)
        if args.command == "view":
            print(buffer.view())
        elif args.command == "history":
            print(json.dumps(state["operations"], indent=2, ensure_ascii=False))
        elif args.command == "commit":
            result = buffer.commit()
            state["committed"] = True
            _save(state_path, state)
            print(result)
        elif args.command == "rollback":
            operation = {"op": "rollback", "version": args.version}
            buffer.apply(operation)
            state["operations"].append(operation)
            _save(state_path, state)
        else:
            operation = _operation(args)
            buffer.apply(operation)
            state["operations"].append(operation)
            _save(state_path, state)
        return 0
    except (EditBufferError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"editbuffer: {error}\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="editbuffer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new = subparsers.add_parser("new")
    new.add_argument("state")
    new.add_argument("--text", default="")

    append = subparsers.add_parser("append")
    append.add_argument("state")
    append.add_argument("text")

    replace = subparsers.add_parser("replace")
    replace.add_argument("state")
    replace.add_argument("target", help="selection as JSON")
    replace.add_argument("text")

    apply = subparsers.add_parser("apply")
    apply.add_argument("state")
    apply.add_argument("operation", help="operation as JSON")

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("state")
    rollback.add_argument("version", type=int)

    for name in ("view", "history", "commit"):
        command = subparsers.add_parser(name)
        command.add_argument("state")
    return parser


def _operation(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "append":
        return {"op": "append", "text": args.text}
    if args.command == "replace":
        target = json.loads(args.target)
        if not isinstance(target, dict):
            raise InvalidOperationError("target must be a JSON object")
        return {"op": "replace", "target": target, "text": args.text}
    operation = json.loads(args.operation)
    if not isinstance(operation, dict):
        raise InvalidOperationError("operation must be a JSON object")
    return operation


def _load(path: Path) -> dict[str, Any]:
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise InvalidOperationError("state must be a JSON object")
    return state


def _restore(state: dict[str, Any]) -> EditBuffer:
    initial = state.get("initial")
    operations = state.get("operations")
    if not isinstance(initial, str) or not isinstance(operations, list):
        raise InvalidOperationError("invalid state file")
    buffer = EditBuffer(initial)
    for operation in operations:
        if not isinstance(operation, dict):
            raise InvalidOperationError("invalid operation in state file")
        buffer.apply(operation)
    if state.get("committed"):
        buffer.commit()
    return buffer


def _save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    )
    try:
        with handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
