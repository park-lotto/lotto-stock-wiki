from .common import parse_json_fields


def load(ctx):
    if ctx.connection is None:
        return [], "skipped", ("database_not_configured",)
    rows = ctx.rows("spine")
    if rows is None:
        return [], "unavailable", ("spine_table_missing",)
    items = []
    for raw in rows:
        if "customer_id" in raw and raw["customer_id"] is None:
            continue
        owner = ctx.tenant_owner(raw["customer_id"]) if "customer_id" in raw else ctx.company_owner()
        if not owner.permits(ctx.access):
            continue
        row = parse_json_fields(raw)
        items.append(ctx.make(
            "script", row["id"], kind="recipe", domain="script", name=row.get("name"),
            parameters=row, source="spine", owner=owner, status=row.get("status"),
            tags=("script", *(row.get("fit_categories") or ())),
            description=row.get("situation_type") or "",
            constraints=("facts_must_come_from_project_materials", "legacy_approval_is_not_release_approval"),
        ))
    return items, "ok", ()
