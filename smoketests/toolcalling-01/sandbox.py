#!/usr/bin/env python3
"""microVM sandbox helper for toolcalling-01 smoke test.

Boots a microsandbox (microVM via cloud-hypervisor/KVM), probes readiness, runs
Python code inside, and tears down.  Used by executor.py for the sandbox
execution mode.

Sandbox lifecycle:
  boot_sandbox()  -> Sandbox handle (async)
  run_python(sb)  -> ExecOutput   (async)
  stop_and_remove() -> None        (sync, static Sandbox.remove)
"""

import asyncio
import logging
import time

from microsandbox import Sandbox, SandboxAlreadyExistsError
from microsandbox.types import ExecOutput, Network, NetworkPolicy

SANDBOX_NAME = "cheap-toolcalling"
SANDBOX_IMAGE = "python"
KILL_TIMEOUT_S = 30
PROBE_TIMEOUT_S = 60
POLL_INTERVAL_S = 2
LOG = logging.getLogger(__name__)


class SandboxContext:
    sandbox: Sandbox | None
    name: str

    def __init__(self, name: str = SANDBOX_NAME) -> None:
        self.name = name
        self.sandbox = None


async def boot_sandbox(ctx: SandboxContext) -> Sandbox:
    """Create (or reuse) a sandbox and store it on *ctx*."""
    LOG.info("booting sandbox %r (image=%r) ...", ctx.name, SANDBOX_IMAGE)
    try:
        sb = await Sandbox.create(
            image=SANDBOX_IMAGE,
            name=ctx.name,
            replace=True,
            network=Network(policy=NetworkPolicy.none()),
        )
    except SandboxAlreadyExistsError:
        LOG.warning("sandbox %r already exists; reusing", ctx.name)
        sb = Sandbox(name=ctx.name)
    ctx.sandbox = sb
    LOG.info("sandbox %r ready (id=%s)", ctx.name, sb.id)
    return sb


def sandbox_ready(ctx: SandboxContext, timeout: int = PROBE_TIMEOUT_S) -> bool:
    """Synchronous probe: try to exec a no-op inside the sandbox."""

    async def _probe():
        sb = ctx.sandbox or await boot_sandbox(ctx)
        result = await sb.exec(["echo", "ready"], timeout=10)
        return result.success

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return asyncio.run(_probe())
        except Exception as exc:  # noqa: BLE001
            LOG.debug("sandbox probe failed: %s; retrying …", exc)
            time.sleep(POLL_INTERVAL_S)
    LOG.error("sandbox not ready after %ss", timeout)
    return False


async def run_python(ctx: SandboxContext, code: str, timeout: int = 30) -> ExecOutput:
    """Run *code* via ``python3 -c`` inside the sandbox."""
    sb = ctx.sandbox
    if sb is None:
        raise RuntimeError("sandbox not booted; call boot_sandbox() first")
    return await sb.exec(["python3", "-c", code], timeout=timeout)


def stop_and_remove(ctx: SandboxContext) -> None:
    """Stop and remove the sandbox (static Sandbox.remove)."""
    if ctx.sandbox is not None:
        LOG.info("removing sandbox %r ...", ctx.name)
        asyncio.run(ctx.sandbox.stop())
        Sandbox.remove(ctx.name)
        ctx.sandbox = None
        LOG.info("sandbox %r removed", ctx.name)
