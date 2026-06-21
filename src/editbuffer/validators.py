import json
import subprocess

from .errors import ValidationError


def valid_json(content: str) -> None:
    try:
        json.loads(content)
    except json.JSONDecodeError as error:
        raise ValidationError(str(error)) from error


def valid_shell(content: str) -> None:
    result = subprocess.run(
        ["sh", "-n"],
        input=content,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValidationError(result.stderr.strip() or "invalid shell syntax")
