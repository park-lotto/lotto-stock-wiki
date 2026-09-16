from ..schema import Dependency
from .common import artifact, item_id, read_json


def load(ctx):
    base = ctx.config.repo / "shopping_shorts/assets/motion"
    items = []
    for row in read_json(base / "manifest.json")["assets"]:
        filename = row.get("file") or ""
        items.append(ctx.make(
            "motion", row["id"], kind="asset", domain="motion", name=row.get("name") or row["id"],
            parameters=row, source="motion/manifest.json",
            artifacts=(artifact(filename, base, "repo:shopping_shorts/assets/motion/" + filename),),
            tags=(row.get("type"), "motion"),
            constraints=("alpha_and_playback_unverified",),
        ))
    for row in read_json(base / "packs.json")["packs"]:
        dependencies = []
        for key in ("transition", "sticker"):
            aid = (row.get(key) or {}).get("asset_id")
            if aid:
                dependencies.append(Dependency(item_id("motion", aid)))
        items.append(ctx.make(
            "motion-pack", row["id"], kind="pack", domain="motion", name=row.get("name"),
            parameters=row, source="motion/packs.json", dependencies=dependencies,
            tags=("pack", row.get("intensity")),
        ))
    return items, "ok", ()
