from .common import artifact, read_json


def load(ctx):
    base = ctx.config.repo / "shopping_shorts/static"
    rows = read_json(base / "fonts.json")
    if not isinstance(rows, list):
        raise ValueError("fonts.json must contain an array")
    items = []
    for row in rows:
        filename = row["file"]
        items.append(ctx.make(
            "font", filename, kind="asset", domain="font", name=row.get("name"),
            parameters=row, source="fonts.json", aliases=(row.get("css"),),
            artifacts=(artifact(filename, base / "fonts", "repo:shopping_shorts/static/fonts/" + filename),),
            tags=(row.get("group"), "font"),
            constraints=("glyph_coverage_unverified", "renderer_support_unverified"),
        ))
    return items, "ok", ()
