"""Repetibilidade das odometrias visuais — docs/protocol_vo_repeat.md, seções 5–7.

Compara execuções só pelas saídas das próprias VOs (nunca o GT), no frame nativo `cam_left`:
integridade (5.1), disponibilidade/segmentação (A), incrementos (B), poses ancoradas por
sobreposição de segmentos (C), hashes (5.6) e regra de decisão (6).
"""
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import se3, tracks

ARTIFACTS = ("frames.csv", "poses_causal.tum", "state.csv", "indicators.csv", "run.json")
HASHED = ("poses_causal.tum", "state.csv", "indicators.csv")
INDICATORS = ("inliers", "n_features", "reproj_err", "tracked_ratio")
TRANS_LIMIT_M = 0.001
ROT_LIMIT_DEG = 0.01


def _read_table(path, integral, numeric):
    """Lê um CSV sem lançar exceção; devolve (tabela, motivo).

    Colunas `integral` exigem tipo inteiro (sem frações nem ausentes): um instante 1,9 não pode ser truncado para 1,
    nem um map_id ausente pode criar segmentação. Colunas `numeric` aceitam ausentes (indicadores).
    """
    try:
        df = pd.read_csv(path)
    except Exception as e:  # CSV malformado, binário, vazio
        return None, f"{path.name}: ilegível ({type(e).__name__})"
    missing = [c for c in (*integral, *numeric) if c not in df.columns]
    if missing:
        return None, f"{path.name}: colunas ausentes {missing}"
    bad = [c for c in integral if not pd.api.types.is_integer_dtype(df[c])]
    bad += [c for c in numeric if not pd.api.types.is_numeric_dtype(df[c])]
    if bad:
        return None, f"{path.name}: valores inválidos em {bad}"
    return df, None


def validate_run(run_dir, canonical_ts, exit_code):
    """Seção 5.1: devolve (válida, motivos); artefatos malformados tornam a execução inválida."""
    run_dir = Path(run_dir)
    reasons = []
    if exit_code is None:
        reasons.append("registro de execução ausente, ilegível ou incompleto")
    elif exit_code != 0:
        reasons.append(f"código de saída {exit_code}")
    missing = [a for a in ARTIFACTS if not (run_dir / a).exists()]
    if missing:
        reasons.append(f"artefatos ausentes: {missing}")
        return False, reasons
    state, why_s = _read_table(run_dir / "state.csv", ["ts_ns", "ok", "map_id"], [])
    ind, why_i = _read_table(run_dir / "indicators.csv", ["ts_ns"], list(INDICATORS))
    reasons += [w for w in (why_s, why_i) if w]
    if state is not None and not state["ok"].isin([0, 1]).all():
        reasons.append("state.csv: ok fora de {0, 1}")
        state = None
    canonical = np.sort(np.asarray(canonical_ts, dtype=np.int64))
    for name, df in (("state.csv", state), ("indicators.csv", ind)):
        if df is None:
            continue
        ts = np.sort(df["ts_ns"].to_numpy(dtype=np.int64))
        if len(np.unique(ts)) != len(ts):
            reasons.append(f"{name}: instantes duplicados")
        elif not np.array_equal(ts, canonical):
            reasons.append(f"{name}: instantes diferentes da grade canônica "
                           f"({len(ts)} contra {len(canonical)})")
    try:
        pose_ts, pose_Ts = se3.load_tum(run_dir / "poses_causal.tum")
    except Exception as e:
        reasons.append(f"poses_causal.tum: ilegível ({type(e).__name__})")
        return False, reasons
    if not np.isfinite(pose_Ts).all():
        reasons.append("poses_causal.tum: poses com valores não finitos")
    if state is not None:
        ok_ts = np.sort(state.loc[state["ok"] == 1, "ts_ns"].to_numpy(dtype=np.int64))
        if len(np.unique(pose_ts)) != len(pose_ts):
            reasons.append("poses_causal.tum: instantes duplicados")
        elif not np.array_equal(np.sort(pose_ts), ok_ts):
            reasons.append("poses_causal.tum: instantes não coincidem com os quadros ok = 1")
    return not reasons, reasons


def run_hashes(run_dir):
    return {f"sha256_{name}": hashlib.sha256((Path(run_dir) / name).read_bytes()).hexdigest()
            for name in HASHED}


def _load(run_dir):
    run_dir = Path(run_dir)
    state = pd.read_csv(run_dir / "state.csv").sort_values("ts_ns").reset_index(drop=True)
    seg = tracks.segments_from_state(state)["segment"].to_numpy()
    ts, Ts = se3.load_tum(run_dir / "poses_causal.tum")
    poses = {int(t): T for t, T in zip(ts, Ts)}
    return state["ts_ns"].to_numpy(np.int64), state["ok"].to_numpy(int), seg, poses


def _starts(ts, seg):
    return {int(ts[i]) for i in range(len(seg)) if seg[i] >= 0 and (i == 0 or seg[i] != seg[i - 1])}


def _failures(ok):
    """Mesma definição do pipeline (ofd.evaluate.coverage): transições ok 1 → 0."""
    return int(np.sum((ok[:-1] == 1) & (ok[1:] == 0)))


def _resets(seg):
    """Mesma definição do pipeline: número de segmentos menos um."""
    return max(0, len(np.unique(seg[seg >= 0])) - 1)


def _join(values):
    return ";".join(str(int(v)) for v in values)


def _max_delta(deltas):
    if not deltas:
        return np.nan, np.nan
    return (float(max(np.linalg.norm(d[:3, 3]) for d in deltas)),
            float(max(np.degrees(se3.rot_angle(d)) for d in deltas)))


def compare_pair(run_a, run_b):
    """Componentes A, B e C entre duas execuções válidas."""
    ts, ok_a, seg_a, Pa = _load(run_a)
    ts_b, ok_b, seg_b, Pb = _load(run_b)
    if not np.array_equal(ts, ts_b):
        raise ValueError("execuções com grades diferentes; validar antes de comparar")
    both = (ok_a == 1) & (ok_b == 1)
    diverge = ok_a != ok_b
    n_ok_diverge = int(np.sum(diverge))
    starts_a, starts_b = _starts(ts, seg_a), _starts(ts, seg_b)
    boundaries_differ = starts_a != starts_b

    inc = []
    for i in range(1, len(ts)):
        if both[i - 1] and both[i] and seg_a[i] == seg_a[i - 1] and seg_b[i] == seg_b[i - 1]:
            t0, t1 = int(ts[i - 1]), int(ts[i])
            inc.append(se3.delta(se3.delta(Pa[t0], Pa[t1]), se3.delta(Pb[t0], Pb[t1])))
    b_t, b_r = _max_delta(inc)

    anchored, n_overlaps = [], 0
    idx = np.flatnonzero(both)
    for _, group in itertools.groupby(idx, key=lambda i: (seg_a[i], seg_b[i])):
        group = list(group)
        if len(group) < 2:
            continue
        n_overlaps += 1
        t0 = int(ts[group[0]])
        Aa, Ab = se3.inv(Pa[t0]), se3.inv(Pb[t0])
        for i in group:
            t = int(ts[i])
            anchored.append(se3.delta(Aa @ Pa[t], Ab @ Pb[t]))
    c_t, c_r = _max_delta(anchored)

    return {"A_identical": bool(n_ok_diverge == 0 and not boundaries_differ),
            "A_n_ok_diverge": n_ok_diverge, "A_boundaries_differ": bool(boundaries_differ),
            "A_coverage_diff": float(abs(ok_a.mean() - ok_b.mean())),
            "A_n_segments_a": int(seg_a.max() + 1) if (seg_a >= 0).any() else 0,
            "A_n_segments_b": int(seg_b.max() + 1) if (seg_b >= 0).any() else 0,
            "A_failures_a": _failures(ok_a), "A_failures_b": _failures(ok_b),
            "A_resets_a": _resets(seg_a), "A_resets_b": _resets(seg_b),
            "A_ok_diverge_ts": _join(ts[diverge]),
            "A_boundaries_only_a": _join(sorted(starts_a - starts_b)),
            "A_boundaries_only_b": _join(sorted(starts_b - starts_a)),
            "B_n": len(inc), "B_max_t_m": b_t, "B_max_r_deg": b_r,
            "C_n": len(anchored), "C_n_overlaps": n_overlaps, "C_max_t_m": c_t, "C_max_r_deg": c_r}


def _below(value, limit):
    return bool(np.isfinite(value) and value < limit)


def read_record(path):
    """Registro externo de uma execução: (código de saída, situação), sem lançar exceção.

    Situações: finished, missing, unreadable (JSON inválido ou não objeto) e incomplete (status diferente
    de "finished", inclusive ausente ou desconhecido, ou código de saída não inteiro).
    """
    path = Path(path)
    if not path.exists():
        return None, "missing"
    try:
        rec = json.loads(path.read_text())
    except (ValueError, OSError):
        return None, "unreadable"
    if not isinstance(rec, dict):
        return None, "unreadable"
    code = rec.get("exit_code")
    if rec.get("status") != "finished" or not isinstance(code, int) or isinstance(code, bool):
        return None, "incomplete"
    return code, "finished"


def analyze_combination(run_dirs, canonical_ts, exit_codes, record_status=None):
    """Seção 6 para uma combinação método × sequência; todos os pares de execuções."""
    if len(run_dirs) != len(exit_codes):
        raise ValueError("um código de saída por execução")
    if len(run_dirs) < 2:
        raise ValueError("a regra da seção 6 exige ao menos duas execuções")
    rows = []
    for k, (path, code) in enumerate(zip(run_dirs, exit_codes), 1):
        valid, reasons = validate_run(path, canonical_ts, code)
        hashes = run_hashes(path) if valid else {f"sha256_{n}": None for n in HASHED}
        rows.append({"repetition": k, "path": str(path), "exit_code": code,
                     "record_status": record_status[k - 1] if record_status else None, "valid": valid,
                     "reasons": "; ".join(reasons), **hashes})
    runs = pd.DataFrame(rows)

    pairs = []
    for (i, a), (j, b) in itertools.combinations(enumerate(run_dirs, 1), 2):
        base = {"rep_a": i, "rep_b": j}
        if runs.loc[i - 1, "valid"] and runs.loc[j - 1, "valid"]:
            pairs.append({**base, **compare_pair(a, b)})
        else:
            pairs.append({**base, "A_identical": np.nan, "B_n": np.nan, "B_max_t_m": np.nan,
                          "B_max_r_deg": np.nan, "C_n": np.nan, "C_max_t_m": np.nan, "C_max_r_deg": np.nan})
    pairs = pd.DataFrame(pairs)

    if not runs["valid"].all():
        decision = "variable"
    elif all(runs[f"sha256_{n}"].nunique() == 1 for n in HASHED):
        decision = "deterministic"
    elif runs["sha256_indicators.csv"].nunique() == 1 and all(
            p.A_identical and p.B_n > 0 and p.C_n > 0
            and _below(p.B_max_t_m, TRANS_LIMIT_M) and _below(p.B_max_r_deg, ROT_LIMIT_DEG)
            and _below(p.C_max_t_m, TRANS_LIMIT_M) and _below(p.C_max_r_deg, ROT_LIMIT_DEG)
            for p in pairs.itertuples()):
        decision = "numerically_equivalent"
    else:
        decision = "variable"
    return {"decision": decision, "runs": runs, "pairs": pairs}


BASE_REPS = [1, 2, 3]
ESCALATED_REPS = list(range(1, 11))


def reps_plan(decisions):
    """Repetições por combinação: r1–r10 só nas variáveis da fase 1, r1–r3 nas demais (seção 6)."""
    return {tuple(key.split("/")): (ESCALATED_REPS if d == "variable" else BASE_REPS)
            for key, d in decisions.items()}


def phase1(plan, runs_root, extracted_root, log_dir, out_dir):
    """Seção 6 para cada combinação {(seq, método): [k, ...]}; grava execuções, pares e decisões.

    Sem GT e sem métricas de erro.
    """
    runs_root, extracted_root, log_dir, out_dir = map(Path, (runs_root, extracted_root, log_dir, out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    decisions = {}
    for (seq, method), reps in plan.items():
        canonical = pd.read_csv(extracted_root / seq / "images" / "stamps.csv")["ts_ns"].to_numpy(np.int64)
        dirs, codes, status = [], [], []
        for k in reps:
            dirs.append(runs_root / seq / f"{method}_r{k}")
            code, st = read_record(log_dir / f"{seq}_{method}_r{k}.json")
            codes.append(code)
            status.append(st)
        res = analyze_combination(dirs, canonical, codes, status)
        res["runs"].to_csv(out_dir / f"{seq}_{method}_runs.csv", index=False)
        res["pairs"].to_csv(out_dir / f"{seq}_{method}_pairs.csv", index=False)
        decisions[f"{seq}/{method}"] = res["decision"]
    (out_dir / "decisions.json").write_text(json.dumps(decisions, indent=2))
    return decisions


def describe(values, kind):
    """Seção 7: estatística fixada por métrica; valores indefinidos (NaN) ficam de fora."""
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    n = len(v)
    out = {"n_defined": n, "min": float(v.min()) if n else np.nan, "max": float(v.max()) if n else np.nan}
    if kind == "mean_sd":
        out.update(mean=float(v.mean()) if n else np.nan, sd=float(v.std(ddof=1)) if n >= 2 else np.nan)
    elif kind == "median_iqr":
        q1, med, q3 = np.percentile(v, [25, 50, 75], method="linear") if n else (np.nan,) * 3
        out.update(median=float(med), q1=float(q1), q3=float(q3))
    else:
        raise ValueError(f"estatística desconhecida: {kind}")
    return out


def indicator_medians(run_dir):
    """Por execução: mediana de cada indicador nos quadros ok = 1 e fração ausente nesses quadros."""
    run_dir = Path(run_dir)
    state = pd.read_csv(run_dir / "state.csv")
    ind = pd.read_csv(run_dir / "indicators.csv")
    okf = state.loc[state["ok"] == 1, ["ts_ns"]].merge(ind, on="ts_ns", how="left", validate="one_to_one")
    out = {}
    for col in INDICATORS:
        vals = okf[col].to_numpy(dtype=np.float64)
        defined = vals[np.isfinite(vals)]
        out[f"{col}_median"] = float(np.median(defined)) if len(defined) else np.nan
        out[f"{col}_missing_frac"] = float(1 - len(defined) / len(vals)) if len(vals) else np.nan
    return out


def main():
    import argparse
    from ofd.run_vo_repeat import LOG_DIR, METHODS, SEQUENCES
    ap = argparse.ArgumentParser(description="Fase 1 do protocolo das VOs: repetibilidade, sem métricas de erro")
    ap.add_argument("--from-decisions", help="decisions.json das 3 execuções: analisa r1–r10 só nas variáveis")
    ap.add_argument("--out", required=True, help="ex.: data/analysis/vo_repeat/phase1")
    a = ap.parse_args()
    if a.from_decisions:
        plan = reps_plan(json.loads(Path(a.from_decisions).read_text()))
    else:
        plan = {(s, m): BASE_REPS for s in SEQUENCES for m in METHODS}
    decisions = phase1(plan, "data/runs", "data/extracted", LOG_DIR, a.out)
    print(json.dumps(decisions, indent=2))


if __name__ == "__main__":
    main()
