from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from ..schema import Artifact, CatalogItem, LegacyRef, Owner, fingerprint


@contextmanager
def open_readonly(path):
    path = Path(path).resolve(strict=True)
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        yield conn
    finally:
        conn.close()


def item_id(namespace, key):
    return f"legacy/{namespace}/{quote(str(key), safe='-._')}"


def artifact(path, root, uri, role="source"):
    if root is None:
        return Artifact(uri, role, False, issue="media_root_required")
    root = Path(root).resolve()
    path = Path(path)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(root):
        return Artifact(uri, role, False, issue="path_outside_root")
    if not path.is_file():
        return Artifact(uri, role, False, issue="file_missing")
    try:
        hasher = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
                size += len(chunk)
        return Artifact(uri, role, True, hasher.hexdigest(), size)
    except OSError:
        return Artifact(uri, role, False, issue="file_unreadable")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def parse_json_fields(row):
    result = dict(row)
    for key, value in list(result.items()):
        if key.endswith("_json"):
            result[key[:-5]] = json.loads(value) if value else None
            del result[key]
    return result


@dataclass
class AdapterContext:
    config: object
    access: object
    connection: object = None

    def company_owner(self):
        return Owner(self.config.company_id)

    def tenant_owner(self, tenant):
        return Owner(self.config.company_id, "tenant", str(tenant))

    def rows(self, table, owner_column=None, zero_is_shared=False):
        if table not in ("scene_assets", "spine", "voice_presets"):
            raise ValueError("unsupported legacy table")
        if self.connection is None:
            return None
        exists = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            return None
        columns = {row[1] for row in self.connection.execute(f'PRAGMA table_info("{table}")')}
        sql = f'SELECT * FROM "{table}"'
        values = []
        if owner_column:
            if owner_column not in ("customer_id", "owner_customer_id"):
                raise ValueError("unsupported owner column")
            if owner_column not in columns:
                # An older DB without ownership metadata is not publicly readable.
                return []
            if not self.access.is_admin:
                clauses = []
                if zero_is_shared:
                    clauses.append(f'"{owner_column}"=0')
                if self.access.tenant_id is not None:
                    clauses.append(f'CAST("{owner_column}" AS TEXT)=?')
                    values.append(self.access.tenant_id)
                if not clauses:
                    return []
                sql += " WHERE " + " OR ".join(clauses)
        return [dict(row) for row in self.connection.execute(sql, values)]

    def make(self, namespace, key, *, kind, domain, name, parameters,
             source, owner=None, status=None, aliases=(), artifacts=(),
             dependencies=(), tags=(), description="", capabilities=(), constraints=(),
             locale=(), source_fingerprint=None):
        identity = item_id(namespace, key)
        owner = owner or self.company_owner()
        refs = (LegacyRef(source, str(key)),) + tuple(LegacyRef(source, str(a)) for a in aliases if a)
        version = fingerprint({
            "id": identity, "owner": asdict(owner), "parameters": parameters,
            "artifacts": [asdict(a) for a in artifacts],
            "source_fingerprint": source_fingerprint,
        })
        return CatalogItem(
            id=identity, kind=kind, domain=domain, name=str(name or key), version=version,
            owner=owner, status=str(status or "legacy_unreviewed"), description=description,
            parameters=parameters, source_refs=(source,), legacy_refs=refs,
            artifacts=tuple(artifacts), dependencies=tuple(dependencies),
            tags=tuple(str(t) for t in tags if t), locale=tuple(locale),
            capabilities=tuple(capabilities), constraints=tuple(constraints),
        )
