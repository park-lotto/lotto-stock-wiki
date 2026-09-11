"""Deterministic effect-signal measurement and candidate derivation."""

from __future__ import annotations


class RepositorySignalAnalyzer:
    name = "cut-motion"

    def __call__(self, media_path):
        from shopping_shorts import scene_cut

        fps = scene_cut.video_fps(media_path)
        cuts = scene_cut.detect_cuts(media_path)
        motion = scene_cut.frame_motion(media_path)
        labeled = scene_cut.cut_motion(cuts, motion)
        rows = []
        for cut in labeled:
            rows.append({
                "start_sec": round(cut["start"] / fps, 4),
                "end_sec": round(cut["end"] / fps, 4),
                "peak_sec": round(cut["peak_frame"] / fps, 4),
                "motion_energy": float(cut["energy"]),
                "motion_level": cut["level"],
            })
        return {
            "duration_sec": rows[-1]["end_sec"] if rows else 0.0,
            "fps": fps,
            "cuts": rows,
        }


def derive_candidates(signal):
    cuts = signal.get("cuts") or []
    out = []
    duration = float(signal.get("duration_sec") or 0.0)
    for cut in cuts[1:]:
        at = float(cut["start_sec"])
        out.append({
            "kind": "scene_transition",
            "start_sec": round(max(0.0, at - 0.15), 3),
            "end_sec": round(min(duration, at + 0.15), 3),
            "score": 0.6,
            "evidence": {"boundary_sec": at},
        })
    for cut in cuts:
        if cut.get("motion_level") != "PEAK":
            continue
        at = float(cut.get("peak_sec") or cut["start_sec"])
        energy = float(cut.get("motion_energy") or 0.0)
        if energy <= 0.0:
            continue
        out.append({
            "kind": "motion_peak",
            "start_sec": round(max(0.0, at - 0.2), 3),
            "end_sec": round(min(duration, at + 0.2), 3),
            "score": round(min(1.0, 0.5 + energy / 100.0), 3),
            "evidence": {"peak_sec": at, "motion_energy": energy},
        })
    return out
