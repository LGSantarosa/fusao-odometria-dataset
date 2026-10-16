"""Fase 2 do protocolo do KISS-ICP (docs/protocol_kissicp.md): consolida as saídas de ofd.kissicp_analysis.

Não executa o estimador. Usa somente a repetição 1 de cada condição (regra da liberação de 15/10/2026).
- BotanicGarden (com GT): critérios de promoção (seção 8, literal, só D1–D3), estratificação do RPE por quadro por
  quartis de movimento (seção 6, pré-registrada) e, marcada como post hoc, a mesma estratificação em janelas de 10 m
  com as medidas de estrutura de H3 (seção 7).
- RELLIS (sem GT, veredito C): apenas descritivo — percurso, regularidade do passo e divergência em relação a D0.

uso: python -m tools.kissicp_phase2 [--root data/analysis/kissicp/phase2]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import se3, tracks
from ofd.kissicp_analysis import promotion_checks

BOTANIC = ("1018-00", "1018-13")
RELLIS = ("rellis_example", "00000")
CONDITIONS = ("D0", "D1", "D2", "D3", "D4", "D4prime")
REGRESSORS = ("omega_dt_rad", "abs_delta_omega_rad_s", "v_dt_m")
STRUCTURE = ("n_voxels_1m", "pca_linearity", "pca_planarity", "pca_scattering",
             "fitness", "inlier_rmse", "unmatched_ratio")


def _rmse(v):
    v = np.asarray(v, dtype=np.float64)
    return float(np.sqrt(np.mean(v ** 2))) if len(v) else np.nan


def relative_to_d0(table, metrics):
    base = table[table.condition == "D0"].set_index("sequence")[metrics]
    rows = []
    for cond in CONDITIONS[1:]:
        c = table[table.condition == cond].set_index("sequence")[metrics]
        rel = (100.0 * (c / base - 1.0)).reset_index()
        rel.insert(1, "condition", cond)
        rows.append(rel)
    return pd.concat(rows, ignore_index=True)


def quartile_table(df, key, error_cols):
    """RMSE por quartil de `key`; D0 absoluto, demais condições em % relativo a D0."""
    q = pd.qcut(df[key], 4, labels=False, duplicates="drop")
    out = []
    for err, cols in error_cols.items():
        t = df.groupby(q)[list(cols.values())].agg(_rmse)
        t.columns = list(cols.keys())
        rel = 100.0 * (t.div(t["D0"], axis=0) - 1.0)
        rel["D0"] = t["D0"]
        rel = rel[list(cols.keys())].reset_index().rename(columns={key: "quartile"})
        rel.insert(0, "error", err)
        rel.insert(0, "regressor", key)
        out.append(rel)
    return pd.concat(out, ignore_index=True)


def frame_strata(seq_dir):
    d = pd.read_csv(seq_dir / "rpe_frame_stratified.csv")
    wide = d.pivot_table(index="end_ts_ns", columns="condition", values=["error_t_m", "error_r_deg"])
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    motion = d.drop_duplicates("end_ts_ns").set_index("end_ts_ns")[list(REGRESSORS)]
    wide = wide.join(motion)
    cols = {e: {c: f"{e}_{c}" for c in CONDITIONS} for e in ("error_t_m", "error_r_deg")}
    return pd.concat([quartile_table(wide, r, cols) for r in REGRESSORS], ignore_index=True)


def window_features(seq_dir):
    """Janelas de 10 m (mesmos pares em todas as condições) com movimento e estrutura médios de D0."""
    w = pd.read_csv(seq_dir / "rpe_10m.csv")
    motion = pd.read_csv(seq_dir / "motion.csv").sort_values("ts_ns")
    structure = pd.read_csv(seq_dir / "structure_d0.csv").sort_values("ts_ns")
    wide = w.pivot_table(index=["start_ts_ns", "end_ts_ns"], columns="condition",
                         values=["error_t_m", "error_r_deg"])
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()
    rows = []
    for a, b in zip(wide.start_ts_ns, wide.end_ts_ns):
        mm = motion[(motion.ts_ns > a) & (motion.ts_ns <= b)]
        ss = structure[(structure.ts_ns > a) & (structure.ts_ns <= b)]
        rows.append({"mean_omega_dt_deg": float(np.degrees(mm.omega_dt_rad.mean())),
                     "max_abs_delta_omega_rad_s": float(mm.abs_delta_omega_rad_s.max()),
                     "mean_v_dt_m": float(mm.v_dt_m.mean()),
                     **{c: float(ss[c].mean()) for c in STRUCTURE}})
    return pd.concat([wide, pd.DataFrame(rows)], axis=1)


def window_strata(win):
    cols = {e: {c: f"{e}_{c}" for c in CONDITIONS} for e in ("error_t_m", "error_r_deg")}
    return pd.concat([quartile_table(win, k, cols)
                      for k in ("mean_omega_dt_deg", "max_abs_delta_omega_rad_s")], ignore_index=True)


def q1_localization(win):
    """Top 10% das janelas por erro de D0 contra o seu complemento; Spearman descritivo (não causal).

    Cada grupo de topo (rotacional, translacional) é comparado com o próprio complemento.
    """
    feats = ["mean_omega_dt_deg", "max_abs_delta_omega_rad_s", "mean_v_dt_m", *STRUCTURE]
    top_r = win.error_r_deg_D0 >= win.error_r_deg_D0.quantile(0.9)
    top_t = win.error_t_m_D0 >= win.error_t_m_D0.quantile(0.9)
    med = pd.DataFrame({"top10_rot": win.loc[top_r, feats].median(),
                        "rest_rot": win.loc[~top_r, feats].median(),
                        "top10_trans": win.loc[top_t, feats].median(),
                        "rest_trans": win.loc[~top_t, feats].median()})
    rho = win[feats + ["error_r_deg_D0", "error_t_m_D0"]].corr("spearman").loc[
        feats, ["error_r_deg_D0", "error_t_m_D0"]]
    return med.join(rho.rename(columns={"error_r_deg_D0": "spearman_r", "error_t_m_D0": "spearman_t"}))


def rellis_descriptive(seq):
    rows = []
    d0 = tracks.load_run(Path("data/runs") / seq / "kissicp_D0_r1")[0]
    for cond in CONDITIONS[:4]:
        tr = tracks.load_run(Path("data/runs") / seq / f"kissicp_{cond}_r1")[0]
        step = np.linalg.norm(np.diff(tr.Ts[:, :3, 3], axis=0), axis=1)
        pos = {int(t): i for i, t in enumerate(d0.ts_ns)}
        idx = [(i, pos[int(t)]) for i, t in enumerate(tr.ts_ns) if int(t) in pos]
        div_t, div_r = [], []
        for (i0, j0), (i1, j1) in zip(idx[:-1], idx[1:]):
            e = se3.delta(se3.delta(d0.Ts[j0], d0.Ts[j1]), se3.delta(tr.Ts[i0], tr.Ts[i1]))
            div_t.append(np.linalg.norm(e[:3, 3]))
            div_r.append(np.degrees(se3.rot_angle(e)))
        state = pd.read_csv(Path("data/runs") / seq / f"kissicp_{cond}_r1" / "state.csv")
        rows.append({"sequence": seq, "condition": cond, "n_poses": len(tr.ts_ns),
                     "coverage": float(state.ok.mean()),
                     "path_m": float(step.sum()), "step_std_cm": float(100 * step.std()),
                     "frame_divergence_vs_D0_t_cm_rmse": 100 * _rmse(div_t),
                     "frame_divergence_vs_D0_r_deg_rmse": _rmse(div_r)})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="data/analysis/kissicp/phase2")
    root = Path(ap.parse_args().root)
    metrics = ["rpe_t_10m", "rpe_r_10m_deg", "ate_rmse", "rpe_t_frame", "rpe_r_frame_deg",
               "error_t_100m_pct", "error_r_100m_deg", "first_100m_ate_rmse"]
    summary = pd.concat([pd.read_csv(root / s / "summary.csv") for s in BOTANIC], ignore_index=True)
    summary.to_csv(root / "summary_all.csv", index=False)
    promotion = promotion_checks(summary)
    promotion.to_csv(root / "promotion.csv", index=False)
    rel = relative_to_d0(summary, metrics)
    rel.to_csv(root / "relative_to_d0_pct.csv", index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print("== Métricas pareadas (repetição 1)\n", summary.round(4).to_string(index=False))
    print("\n== Variação % em relação a D0\n", rel.round(1).to_string(index=False))
    print("\n== Promoção (seção 8, só D1–D3)\n", promotion.to_string(index=False))

    for s in BOTANIC:
        fs = frame_strata(root / s)
        fs.to_csv(root / s / "frame_strata.csv", index=False)
        win = window_features(root / s)
        win.to_csv(root / s / "windows_10m_features.csv", index=False)
        ws = window_strata(win)
        ws.to_csv(root / s / "window_strata_posthoc.csv", index=False)
        q1 = q1_localization(win)
        q1.to_csv(root / s / "q1_localization.csv")
        print(f"\n######## {s}\n== RPE por quadro por quartil (pré-registrado; D0 absoluto, demais % vs D0)\n",
              fs.round(3).to_string(index=False))
        print(f"\n== Janelas de 10 m por quartil (POST HOC)\n", ws.round(3).to_string(index=False))
        print(f"\n== Q1/H3: medianas e Spearman (descritivo)\n", q1.round(4).to_string())

    rellis = pd.concat([rellis_descriptive(s) for s in RELLIS], ignore_index=True)
    rellis.to_csv(root / "rellis_exploratory.csv", index=False)
    print("\n== RELLIS (exploratório, sem GT)\n", rellis.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
