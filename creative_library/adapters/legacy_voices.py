from .common import artifact, parse_json_fields, read_json


def load(ctx):
    base = ctx.config.repo / "shopping_shorts/assets"
    shared = read_json(base / "voice_presets.json")
    rows = [(r, "voice_presets.json") for r in shared]
    file_ids = {r["preset_id"] for r in shared}
    db_rows = ctx.rows("voice_presets", "owner_customer_id", zero_is_shared=True)
    if db_rows:
        # The JSON is the existing source of truth for curated voices; DB is its cache.
        rows.extend((r, "voice_presets") for r in db_rows
                    if not (r.get("origin") == "curated" and r.get("preset_id") in file_ids))
    items = []
    for raw, source in rows:
        tenant = raw.get("owner_customer_id")
        if source == "voice_presets.json" and tenant is None:
            # Only the curated file is allowed to declare a shared default owner.
            if raw.get("origin") != "curated":
                continue
            tenant = 0
        if tenant is None:
            continue
        # Store.list_voice_presets excludes owner=0/library from other customers:
        # the voice lives in the operator's provider account, not a shared account.
        shared_owner = str(tenant) == "0" and raw.get("origin") not in ("library", "tuned")
        owner = ctx.company_owner() if shared_owner else ctx.tenant_owner(tenant)
        if not owner.permits(ctx.access):
            continue
        row = parse_json_fields(raw)
        constraints = ["provider_account_availability_unverified", "voice_usage_rights_unverified"]
        if row.get("origin") == "tuned":
            constraints.append("legacy_picker_hidden")
        if source == "voice_presets" and row.get("origin") == "curated" and row["preset_id"] not in file_ids:
            constraints.append("curated_entry_missing_from_file")
        sample = row.get("sample_file")
        artifacts = (artifact(sample, base / "voice_samples", "repo:shopping_shorts/assets/voice_samples/" + sample, "preview"),) if sample else ()
        items.append(ctx.make(
            "voice", row["preset_id"], kind="recipe", domain="voice", name=row.get("name"),
            parameters=row, source=source, owner=owner, artifacts=artifacts,
            tags=("voice", row.get("variant"), row.get("archetype")),
            description=row.get("one_liner") or "",
            locale=(str(row["lang"]).lower(),) if row.get("lang") else (),
            constraints=constraints,
        ))
    notes = ("database_not_configured: account voices omitted",) if ctx.connection is None else ()
    return items, "ok", notes
