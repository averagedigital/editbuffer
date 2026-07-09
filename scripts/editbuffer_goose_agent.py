from __future__ import annotations

from harbor.agents.installed.goose import Goose
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class EditbufferGoose(Goose):
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        package = self._editbuffer_package()
        hook_enabled = self._editbuffer_hook_enabled()
        await self.exec_as_root(
            environment,
            command="apt-get update && apt-get install -y git",
            env={"DEBIAN_FRONTEND": "noninteractive"},
            timeout_sec=120,
        )
        await self.exec_as_agent(
            environment,
            command=(
                "set -e; "
                "if ! command -v uvx >/dev/null 2>&1; then "
                "curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null; "
                "fi; "
                'export PATH="$HOME/.local/bin:$PATH"; '
                'uv tool install --force "$EDITBUFFER_PACKAGE"; '
                'if [ "$EDITBUFFER_HOOK_ENABLED" = "1" ]; then '
                "mkdir -p ~/.agents/plugins/editbuffer/hooks; "
                "cat > ~/.agents/plugins/editbuffer/plugin.json <<'EOF'\n"
                '{"name":"editbuffer","version":"0.3.0","description":"Record failed goose shell calls in editbuffer history"}\n'
                "EOF\n"
                "cat > ~/.agents/plugins/editbuffer/hooks/hooks.json <<'EOF'\n"
                '{"hooks":{"PostToolUseFailure":[{"matcher":"^developer__shell$","hooks":[{"type":"command","command":"$HOME/.local/bin/editbuffer-hook --provider goose"}]}]}}\n'
                "EOF\n"
                "fi"
            ),
            env={
                "EDITBUFFER_PACKAGE": package,
                "EDITBUFFER_HOOK_ENABLED": hook_enabled,
            },
            timeout_sec=120,
        )
        await super().run(instruction, environment, context)

    def _editbuffer_package(self) -> str:
        package = self._get_env("EDITBUFFER_PACKAGE")
        if not package:
            raise ValueError("EDITBUFFER_PACKAGE must pin the editbuffer build under test")
        return package

    def _editbuffer_hook_enabled(self) -> str:
        enabled = self._get_env("EDITBUFFER_HOOK_ENABLED")
        if enabled not in {"0", "1"}:
            raise ValueError("EDITBUFFER_HOOK_ENABLED must be 0 or 1")
        return enabled
