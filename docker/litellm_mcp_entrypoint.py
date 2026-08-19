"""Wrap the litellm-mcp sidecar so the FastMCP streamable-http server binds 0.0.0.0.

The upstream image (ghcr.io/tetra-2023/litellm-mcp:latest) calls
FastMCP(...).run(transport="streamable-http") with no host, and the pinned
mcp library defaults to 127.0.0.1:8000. Patch the default before the
upstream module builds its singleton so the compose-published 4001:8000
port is actually reachable from the host.
"""

import runpy

from mcp.server.fastmcp import FastMCP

_orig_init = FastMCP.__init__


def _init(self, *args, **kwargs):
    kwargs.setdefault("host", "0.0.0.0")
    return _orig_init(self, *args, **kwargs)


FastMCP.__init__ = _init

runpy.run_path("/app/src/server.py", run_name="__main__")
