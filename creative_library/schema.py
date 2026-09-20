"""Small shared contract; domain parameters remain owned by their legacy source."""
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION


def fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LibraryConfig:
    repo: Path
    db: Path | None = None
    media_root: Path | None = None
    company_id: str = "local"

    def __post_init__(self):
        if not self.company_id:
            raise ValueError("company_id must be nonempty")
        for name in ("repo", "db", "media_root"):
            value = getattr(self, name)
            if value is None:
                continue
            path = Path(value)
            if not path.is_absolute():
                raise ValueError(f"{name} must be an explicit absolute path")
            path = path.resolve(strict=True)
            if name == "db" and not path.is_file():
                raise ValueError("db must be a file")
            if name != "db" and not path.is_dir():
                raise ValueError(f"{name} must be a directory")
            object.__setattr__(self, name, path)


@dataclass(frozen=True)
class AccessContext:
    company_id: str = "local"
    tenant_id: str | int | None = None
    project_id: str | None = None
    is_admin: bool = False

    def __post_init__(self):
        if not self.company_id:
            raise ValueError("company_id must be nonempty")
        if self.tenant_id is not None:
            object.__setattr__(self, "tenant_id", str(self.tenant_id))


@dataclass(frozen=True)
class Owner:
    company_id: str
    scope: str = "company"
    tenant_id: str | None = None
    project_id: str | None = None

    def __post_init__(self):
        if self.scope not in ("company", "tenant", "project"):
            raise ValueError("unknown owner scope")
        if self.scope in ("tenant", "project") and self.tenant_id is None:
            raise ValueError("private owner must identify a tenant")
        if self.scope == "project" and not self.project_id:
            raise ValueError("project owner must identify a project")

    def permits(self, context: AccessContext) -> bool:
        if context.company_id != self.company_id:
            return False
        if context.is_admin or self.scope == "company":
            return True
        return (context.tenant_id == self.tenant_id
                and (self.scope != "project" or context.project_id == self.project_id))


@dataclass(frozen=True)
class LegacyRef:
    source: str
    key: str


@dataclass(frozen=True)
class Artifact:
    uri: str
    role: str
    exists: bool
    sha256: str | None = None
    size_bytes: int | None = None
    issue: str | None = None
    verification: str = "file_hash_only"


@dataclass(frozen=True)
class Rights:
    status: str = "unknown"
    evidence_refs: tuple[str, ...] = ()
    commercial_use: bool | None = None
    redistribution: bool | None = None
    embedding: bool | None = None
    note: str = "Legacy source has no verified per-item rights evidence."


@dataclass(frozen=True)
class Dependency:
    id: str
    version: str | None = None


@dataclass(frozen=True)
class CatalogItem:
    id: str
    kind: str
    domain: str
    name: str
    version: str
    owner: Owner
    status: str = "legacy_unreviewed"
    schema_version: str = SCHEMA_VERSION
    description: str = ""
    tags: tuple[str, ...] = ()
    locale: tuple[str, ...] = ()
    rights: Rights = field(default_factory=Rights)
    source_refs: tuple[str, ...] = ()
    legacy_refs: tuple[LegacyRef, ...] = ()
    artifacts: tuple[Artifact, ...] = ()
    dependencies: tuple[Dependency, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)
    capabilities: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    review_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if self.kind not in ("asset", "recipe", "pack", "evidence"):
            raise ValueError("unknown catalog kind")
        if not self.id or not self.version or not self.name:
            raise ValueError("id, version, and name are required")
        # Reject non-JSON values and non-finite numbers before they reach the CLI.
        fingerprint(self.to_dict())

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Decision:
    usable: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AdapterReport:
    adapter: str
    state: str
    item_count: int
    issues: tuple[str, ...] = ()
