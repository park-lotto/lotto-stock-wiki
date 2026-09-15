from .common import artifact


def load(ctx):
    if ctx.connection is None:
        return [], "skipped", ("database_not_configured",)
    rows = ctx.rows("scene_assets", "customer_id")
    if rows is None:
        return [], "unavailable", ("scene_assets_table_missing",)
    items = []
    for row in rows:
        owner = ctx.tenant_owner(row["customer_id"])
        if not owner.permits(ctx.access):
            continue
        artifacts = []
        for key, role in (("media_path", "source"), ("poster_path", "preview")):
            value = row.get(key)
            if value:
                artifacts.append(artifact(value, ctx.config.media_root, "media:" + str(value), role))
        items.append(ctx.make(
            "scene", row["id"], kind="asset", domain="scene", name=row.get("title"),
            parameters=row, source="scene_assets", owner=owner, artifacts=artifacts,
            tags=(row.get("asset_type"), row.get("role"), row.get("category"), row.get("tone")),
            description=row.get("scene_desc") or "",
            constraints=("legacy_media_rights_unverified",),
        ))
    return items, "ok", ()
