#!/usr/bin/env python3
"""Real tool handlers for toolcalling-01 smoke test.

Replaces the static MOCK_RESPONSES dict when the executor runs in real mode
(sandbox or local).  Each handler receives the arguments dict and returns a
string suitable for the ``content`` field of a tool message.
"""

import ast
import operator
import os

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

FILM_INDEX = {
    "my neighbor totoro": 1988,
    "inception": 2010,
    "iron man": 1995,
    "the incredible hulk": 1995,
    "thor": 2011,
    "captain america: the first avenger": 2011,
    "the avengers": 2012,
    "iron man 2": 2010,
    "guardians of the galaxy": 2014,
    "the dark knight": 2008,
    "batman v superman: dawn of justice": 2016,
    "wonder woman": 2017,
    "aquaman": 2018,
    "the lion king": 1995,
    "frozen": 2013,
    "toy story": 1995,
    "a bug's life": 1995,
    "finding nemo": 2003,
    "the incredibles": 2004,
    "spirited away": 2001,
    "princess mononoke": 1995,
    "kiki's delivery service": 1995,
    "howl's moving castle": 1988,
    "the dark knight rises": 2012,
    "harry potter and the sorcerer's stone": 1995,
}


def safe_eval(expr: str) -> str:
    """Evaluate a safe arithmetic expression via AST."""
    tree = ast.parse(expr.strip(), mode="eval")
    result = _ast_eval(tree.body)
    return str(result)


def _ast_eval(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _ast_eval(node.body)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_ast_eval(node.operand)
    if isinstance(node, ast.BinOp):
        left = _ast_eval(node.left)
        right = _ast_eval(node.right)
        op_func = _ALLOWED_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"unsupported operator: {type(node.op).__name__}")
        return op_func(left, right)
    raise ValueError(f"unsupported expression node: {type(node).__name__}")


def handle_fs_list(path: str) -> str:
    """List filesystem entries at *path* on the host (local) or sandbox."""
    if not os.path.isdir(path):
        return f"error: path not found: {path}"
    entries = sorted(os.listdir(path))[:30]
    return f"Contents of {path} ({len(entries)} entries):\n" + "\n".join(entries)


def handle_lookup_film(title: str, studio: str | None = None) -> str:
    """Look up the release year of a film from the inline index."""
    key = title.strip().lower()
    year = FILM_INDEX.get(key)
    if year is not None:
        studio_part = f" ({studio})" if studio else ""
        return f"{title}{studio_part} was released in {year}."
    return f"film not found: {title}"


def handle_get_weather(location: str) -> str:
    """Stub weather — no real API available."""
    return f"The current weather in {location} is sunny, 22C."


HANDLERS = {
    "calculate": lambda args: safe_eval(args.get("expression", "")),
    "fs_list": lambda args: handle_fs_list(args.get("path", "/")),
    "lookup_film_year": lambda args: handle_lookup_film(
        args.get("title", ""), args.get("studio")
    ),
    "get_weather": lambda args: handle_get_weather(args.get("location", "Unknown")),
}
