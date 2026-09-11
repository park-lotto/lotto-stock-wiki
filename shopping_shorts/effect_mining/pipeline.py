"""Task handlers for the continuous effect-mining pipeline."""

from __future__ import annotations

from pathlib import Path

from shopping_shorts.effect_mining import ANALYZER_VERSION
from shopping_shorts.effect_mining.analyzers import RepositorySignalAnalyzer, derive_candidates
from shopping_shorts.effect_mining.connectors import external_id_from_url, production_connectors


class RepositoryDownloader:
    def __call__(self, item, target_dir):
        from shopping_shorts.media_download import download_any

        result = download_any(item["url"], target_dir)
        return Path(result[0] if isinstance(result, tuple) else result)


class MiningPipeline:
    def __init__(self, db, media_root, connectors=None, downloader=None, analyzer=None,
                 analyzer_version=ANALYZER_VERSION):
        self.db = db
        self.media_root = Path(media_root)
        self.connectors = connectors or production_connectors()
        self.downloader = downloader or RepositoryDownloader()
        self.analyzer = analyzer or RepositorySignalAnalyzer()
        self.analyzer_name = getattr(self.analyzer, "name", "cut-motion")
        self.analyzer_version = analyzer_version

    def execute(self, task, payload, now=None):
        handlers = {
            "discover": self._discover,
            "acquire": self._acquire,
            "measure": self._measure,
            "promote": self._promote,
        }
        if task not in handlers:
            raise ValueError(f"unknown mining task: {task}")
        return handlers[task](payload, now=now)

    def _discover(self, payload, now=None):
        source = self.db.get_source(int(payload["source_id"]))
        if not source:
            raise ValueError(f"missing source: {payload['source_id']}")
        run_id = self.db.start_run(source["id"], now=now)
        found = new = 0
        try:
            rows = self.connectors.get(source["platform"]).discover(source)
            for row in rows:
                url = row.get("url") or ""
                external_id = row.get("external_id") or external_id_from_url(source["platform"], url)
                if not external_id or not url:
                    continue
                found += 1
                metadata = {k: v for k, v in row.items() if k not in ("url", "external_id")}
                item_id, created = self.db.upsert_item(
                    source["platform"], external_id, url, metadata, now=now,
                )
                new += int(created)
                stored = self.db.get_item(item_id)
                media_path = Path(stored["media_path"]) if stored.get("media_path") else None
                if created or media_path is None or not media_path.exists():
                    self.db.enqueue(
                        "acquire", {"item_id": item_id}, f"acquire:item:{item_id}", now=now,
                    )
            self.db.finish_run(run_id, found, new, now=now)
            return {"source_id": source["id"], "found": found, "new": new}
        except Exception as exc:
            self.db.finish_run(run_id, found, new, error=repr(exc), now=now)
            raise

    def _acquire(self, payload, now=None):
        item = self.db.get_item(int(payload["item_id"]))
        if not item:
            raise ValueError(f"missing item: {payload['item_id']}")
        existing = Path(item["media_path"]) if item.get("media_path") else None
        if existing and existing.exists():
            path = existing
        else:
            path = Path(self.downloader(item, self.media_root / item["platform"]))
            if not path.exists():
                raise RuntimeError(f"downloader returned missing file: {path}")
            self.db.set_item_media(item["id"], path, now=now)
        self.db.enqueue(
            "measure", {"item_id": item["id"]},
            f"measure:item:{item['id']}:{self.analyzer_version}", now=now,
        )
        return {"item_id": item["id"], "media_path": str(path)}

    def _measure(self, payload, now=None):
        item = self.db.get_item(int(payload["item_id"]))
        if not item or not item.get("media_path"):
            raise ValueError(f"item has no acquired media: {payload['item_id']}")
        signal = self.db.find_signal(item["id"], self.analyzer_name, self.analyzer_version)
        if signal is None:
            measured = self.analyzer(item["media_path"])
            signal_id = self.db.save_signal(
                item["id"], self.analyzer_name, self.analyzer_version, measured, now=now,
            )
        else:
            signal_id = signal["id"]
        self.db.enqueue(
            "promote", {"signal_id": signal_id}, f"promote:signal:{signal_id}", now=now,
        )
        return {"item_id": item["id"], "signal_id": signal_id}

    def _promote(self, payload, now=None):
        signal = self.db.get_signal(int(payload["signal_id"]))
        if not signal:
            raise ValueError(f"missing signal: {payload['signal_id']}")
        candidates = derive_candidates(signal["signal"])
        for candidate in candidates:
            self.db.add_candidate(signal["item_id"], signal["id"], candidate, now=now)
        return {"signal_id": signal["id"], "candidates": len(candidates)}
