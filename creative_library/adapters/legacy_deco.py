"""Read the existing PRESETS expression without importing application code.

Only the literal registry and its two pure builder functions are evaluated.
Unsupported AST or calls fail closed; helper behavior is never reimplemented.
"""
import ast

from ..schema import Dependency, fingerprint
from .common import item_id


def read_presets(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_hc", "_cap")]
    assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                   and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                   and n.targets[0].id == "PRESETS"]
    if len(assignments) != 1:
        raise ValueError("exactly one PRESETS definition is required")
    selected = ast.Module(body=helpers + assignments, type_ignores=[])
    allowed_calls = {"_hc", "_cap", "min", "bool"}
    for node in ast.walk(selected):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Attribute, ast.Global,
                             ast.Nonlocal, ast.Lambda, ast.ClassDef, ast.With,
                             ast.AsyncFunctionDef, ast.For, ast.While, ast.Try)):
            raise ValueError("unsupported executable expression in preset registry")
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise ValueError("decorated preset builders are not supported")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name)
                                         or node.func.id not in allowed_calls):
            raise ValueError("unsupported call in preset registry")
    scope = {"__builtins__": {"min": min, "bool": bool}}
    exec(compile(selected, str(path), "exec"), scope)
    presets = scope["PRESETS"]
    if not isinstance(presets, dict):
        raise ValueError("PRESETS must be a mapping")
    return presets, fingerprint([ast.dump(n) for n in helpers])


def load(ctx):
    presets, helper_version = read_presets(ctx.config.repo / "shopping_shorts/deco_frame.py")
    items = []
    for key, row in presets.items():
        font = (row.get("headcopy") or {}).get("font")
        dependencies = (Dependency(item_id("font", font)),) if font else ()
        items.append(ctx.make(
            "layout", key, kind="recipe", domain="layout", name=row.get("name"),
            parameters=row, source="deco_frame.PRESETS", dependencies=dependencies,
            source_fingerprint=helper_version,
            tags=("layout", "headcopy" if row.get("headcopy") else "frame"),
            description=row.get("ref") or "",
            constraints=("visual_review_unverified", "source_text_and_watermark_review_required"),
        ))
    return items, "ok", ()
