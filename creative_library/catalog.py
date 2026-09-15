"""One inspection API over six legacy sources, without writes or approval promotion."""
from collections import Counter
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import asdict, replace
import unicodedata

from .adapters import (
    legacy_deco, legacy_fonts, legacy_motion_packs,
    legacy_scene_assets, legacy_spines, legacy_voices,
)
from .adapters.common import AdapterContext, open_readonly
from .schema import AdapterReport, Decision, Dependency, fingerprint

ADAPTERS = (
    ("fonts", legacy_fonts.load),
    ("scene_assets", legacy_scene_assets.load),
    ("motion_packs", legacy_motion_packs.load),
    ("deco", legacy_deco.load),
    ("spines", legacy_spines.load),
    ("voices", legacy_voices.load),
)


class Catalog:
    def __init__(self, items, reports, access):
        self.access = access
        allowed = [deepcopy(item) for item in items if item.owner.permits(access)]
        by_id = {item.id: item for item in allowed}
        if len(by_id) != len(allowed):
            raise ValueError("duplicate catalog identity")
        self._items = self._pin_dependencies(by_id)
        self.reports = tuple(reports)
        self._legacy = {}
        for item in self._items.values():
            for ref in item.legacy_refs:
                key = (ref.source, ref.key)
                if key in self._legacy and self._legacy[key] != item.id:
                    raise ValueError("ambiguous legacy identity")
                self._legacy[key] = item.id
        self.fingerprint = fingerprint([item.to_dict() for item in self.search()])

    @classmethod
    def load(cls, config, access):
        if config.company_id != access.company_id:
            raise PermissionError("catalog company is outside the access context")
        items, reports = [], []
        manager = open_readonly(config.db) if config.db is not None else nullcontext(None)
        # All DB adapters observe one read transaction; file reads do not initialize Store.
        with manager as conn:
            ctx = AdapterContext(config, access, conn)
            for name, loader in ADAPTERS:
                try:
                    loaded, state, issues = loader(ctx)
                    visible = [item for item in loaded if item.owner.permits(access)]
                    if len({i.id for i in visible}) != len(visible):
                        raise ValueError("duplicate adapter identity")
                    items.extend(visible)
                    reports.append(AdapterReport(name, state, len(visible), tuple(issues)))
                except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
                    # Do not dump source rows or private malformed payloads into diagnostics.
                    reports.append(AdapterReport(name, "error", 0, ("adapter_failed:" + type(error).__name__,)))
        return cls(items, reports, access)

    @staticmethod
    def _pin_dependencies(items):
        done = {}

        def visit(key, active):
            if key in done:
                return done[key]
            item = items[key]
            dependencies = []
            for dep in item.dependencies:
                if dep.version is not None:
                    dependencies.append(dep)
                    continue
                target = None if dep.id in (active | {key}) or dep.id not in items else visit(dep.id, active | {key})
                dependencies.append(Dependency(dep.id, target.version if target else None))
            if dependencies and any(d.version is None for d in item.dependencies):
                item = replace(item, dependencies=tuple(dependencies), version=fingerprint({
                    "legacy_version": item.version,
                    "dependencies": [asdict(dep) for dep in dependencies],
                }))
            done[key] = item
            return item

        for key in sorted(items):
            visit(key, set())
        return done

    def get(self, identity):
        item = self._items.get(identity)
        return deepcopy(item) if item and item.owner.permits(self.access) else None

    def get_legacy(self, source, key):
        return self.get(self._legacy.get((source, str(key))))

    def explain(self, identity):
        return self._explain(identity, frozenset())

    def _explain(self, identity, active):
        if identity in active:
            return Decision(False, ("dependency_cycle",))
        item = self.get(identity)
        if item is None:
            return Decision(False, ("not_found_or_not_permitted",))
        reasons = []
        if item.status not in ("approved", "released"):
            reasons.append("not_approved")
        if item.rights.status != "verified" or not item.rights.evidence_refs:
            reasons.append("rights_unverified")
        if item.rights.commercial_use is not True:
            reasons.append("commercial_use_not_verified")
        if not item.review_refs:
            reasons.append("review_unverified")
        if item.constraints:
            reasons.append("constraints_unverified")
        if item.kind == "asset" and not item.artifacts:
            reasons.append("artifact_missing")
        if any(not a.exists for a in item.artifacts):
            reasons.append("artifact_missing")
        for dep in item.dependencies:
            target = self.get(dep.id)
            if target is None or dep.version is None:
                reasons.append("dependency_unresolved")
            if target is not None:
                if dep.version is not None and dep.version != target.version:
                    reasons.append("dependency_version_mismatch")
                child = self._explain(dep.id, active | {identity})
                if not child.usable:
                    reasons.append("dependency_not_usable")
                if "dependency_cycle" in child.reasons:
                    reasons.append("dependency_cycle")
        # A catalog inspection is not proof that a legacy renderer supports the entry.
        if "render_verified" not in item.capabilities:
            reasons.append("compatibility_unverified")
        return Decision(not reasons, tuple(dict.fromkeys(reasons)))

    def search(self, query="", *, domain=None, kind=None, status=None, usable_only=False):
        normalize = lambda s: unicodedata.normalize("NFKC", str(s)).casefold()
        terms = normalize(query).split()
        result = []
        for item in self._items.values():
            if not item.owner.permits(self.access):
                continue
            if domain and item.domain != domain or kind and item.kind != kind or status and item.status != status:
                continue
            haystack = normalize(" ".join((item.id, item.name, item.description, *item.tags)))
            if not all(term in haystack for term in terms):
                continue
            if usable_only and not self.explain(item.id).usable:
                continue
            result.append(deepcopy(item))
        return sorted(result, key=lambda item: item.id)

    def item_dict(self, item):
        return {**item.to_dict(), "eligibility": asdict(self.explain(item.id))}

    def summary(self):
        items = self.search()
        return {
            "mode": "read_only_inspection",
            "fingerprint": self.fingerprint,
            "visible_items": len(items),
            "by_domain": dict(sorted(Counter(i.domain for i in items).items())),
            "by_status": dict(sorted(Counter(i.status for i in items).items())),
            "usable_items": sum(self.explain(i.id).usable for i in items),
            "adapters": [asdict(r) for r in self.reports],
        }

    def to_dict(self):
        return {**self.summary(), "items": [self.item_dict(i) for i in self.search()]}
