"""Per-point time semantics -> times normalized to [0, 1] across the scan (KISS-ICP convention)."""
import numpy as np

UNIT_TO_S = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9}
SPAN_LO, SPAN_HI, MONO_MIN = 0.08, 0.12, 0.99


def _monotonic_frac(rel, ring):
    if rel.size < 2:
        return 0.0
    if ring is None:
        return float(np.mean(np.diff(rel) >= 0))
    ok = tot = 0
    for r in np.unique(ring):
        d = np.diff(rel[ring == r])
        ok += int(np.sum(d >= 0)); tot += d.size
    return ok / tot if tot else 0.0


def normalize(t_raw, unit, ref, scan_stamp_ns, ring=None):
    info = {"t_min_s": np.nan, "t_max_s": np.nan, "span_s": np.nan, "monotonic_frac": 0.0, "valid": False}
    t = np.asarray(t_raw, dtype=np.float64)
    if t.size == 0 or unit not in UNIT_TO_S or ref not in ("scan_start", "scan_end", "absolute"):
        return None, info
    if ref == "absolute":
        rel = t * UNIT_TO_S[unit] - scan_stamp_ns * 1e-9  # ns absoluto em float64: erro ~256 ns, irrelevante
    else:
        rel = t * UNIT_TO_S[unit]  # relativo ao header (scan_end => valores <= 0)
    if not np.all(np.isfinite(rel)):
        return None, info
    info.update(t_min_s=float(rel.min()), t_max_s=float(rel.max()), span_s=float(rel.max() - rel.min()),
                monotonic_frac=_monotonic_frac(rel, None if ring is None else np.asarray(ring)))
    info["valid"] = bool(SPAN_LO <= info["span_s"] <= SPAN_HI and info["monotonic_frac"] >= MONO_MIN)
    if not info["valid"]:
        return None, info
    return (rel - rel.min()) / (rel.max() - rel.min()), info
