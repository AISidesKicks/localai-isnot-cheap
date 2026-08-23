#!/usr/bin/env python3
"""Executor abstraction for toolcalling-01 smoke test.

Resolves which handler runs a tool call:
  - LocalToolExecutor: runs handlers in-process (tools.py).
  - SandboxToolExecutor: ships Python code to a microsandbox microVM.

detect_executor() probes whether a sandbox is available and returns the
appropriate executor.
"""

import asyncio
import logging

from microsandbox.types import ExecOutput

LOG = logging.getLogger(__name__)


class ToolResult:
    def __init__(self, content: str, executor_mode: str = "local") -> None:
        self.content = content
        self.executor_mode = executor_mode


class LocalToolExecutor:
    mode = "local"

    def execute(self, tool_name: str, args: dict) -> str:
        from tools import HANDLERS

        handler = HANDLERS.get(tool_name)
        if handler is None:
            return f"error: unknown tool {tool_name!r}"
        try:
            return handler(args)
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"


class SandboxToolExecutor:
    mode = "sandbox"

    def __init__(self, sandbox_ctx) -> None:
        self._ctx = sandbox_ctx

    def execute(self, tool_name: str, args: dict) -> str:
        from tools import HANDLERS

        handler = HANDLERS.get(tool_name)
        if handler is None:
            return f"error: unknown tool {tool_name!r}"

        if tool_name == "fs_list":
            code = _sandbox_fs_list_code(args.get("path", "/"))
        else:
            try:
                return handler(args)
            except Exception as exc:  # noqa: BLE001
                return f"error: {exc}"

        result = asyncio.run(_exec_python(self._ctx, code))
        if result.success:
            return result.stdout_text or ""
        return f"sandbox error (exit={result.exit_code}): {result.stderr_text or ''}"


def _sandbox_fs_list_code(path: str) -> str:
    import_shlex = "import os, json"
    body = f"entries = sorted(os.listdir({path!r}))[:30]; print(json.dumps(entries))"
    return f"{import_shlex}; {body}"


async def _exec_python(ctx, code: str) -> ExecOutput:
    from sandbox import run_python

    return await run_python(ctx, code)


def detect_executor(sandbox_ctx, prefer: str = "auto") -> tuple:
    """Return (executor, actual_mode) where actual_mode may differ from prefer."""
    if prefer == "local":
        return LocalToolExecutor(), "local"

    from sandbox import boot_sandbox, sandbox_ready, stop_and_remove

    LOG.info("probing microsandbox availability …")
    try:
        asyncio.run(boot_sandbox(sandbox_ctx))
        ready = sandbox_ready(sandbox_ctx)
        if not ready:
            LOG.warning("sandbox probe failed; falling back to local")
            stop_and_remove(sandbox_ctx)
            return LocalToolExecutor(), "local"
        LOG.info("sandbox is ready")
        return SandboxToolExecutor(sandbox_ctx), "sandbox"
    except Exception as exc:  # noqa: BLE001
        LOG.warning("sandbox unavailable (%s); falling back to local", exc)
        return LocalToolExecutor(), "local"
