"""Assemble the per-sequence table on the LiDAR time grid.

Com `blind=True` (modo cego G1), `gt.tum` não é lido e a tabela tem só metadados e features (`schema.blind_schema`).
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, indicators, schema, se3, sync, tracks


def build_sequence(seq_dir, runs_dir, T_L_S, dataset, gt_quality, max_age_ms=100.0, H=10, blind=False):
    seq_dir, runs_dir = Path(seq_dir), Path(runs_dir)
    grid = pd.read_csv(seq_dir / "lidar_stamps.csv")["end_ns"].to_numpy(np.int64)  # instante de disponibilidade
    df = pd.DataFrame({"t": grid, "seq": seq_dir.name, "dataset": dataset, "gt_quality": gt_quality})
    if blind:
        if (seq_dir / "gt.tum").exists():
            raise ValueError(f"modo cego: {seq_dir / 'gt.tum'} existe; extraia com --blind")
    else:
        gt_ts, gt_Ts = se3.load_tum(seq_dir / "gt.tum")
        df = pd.concat([df, sync.gt_deltas(gt_ts, gt_Ts, grid)], axis=1)
    for m, kind in schema.METHODS.items():
        track, ind, meta = tracks.load_run(runs_dir / m)
        md = sync.method_deltas(track, grid, T_L_S[m], max_age_ms)
        err = [] if blind else [sync.method_errors(md, track, T_L_S[m], gt_ts, gt_Ts)]
        cols = schema.VO_IND if kind == "vo" else schema.LO_IND
        src = md["src_ts"].to_numpy()
        ind_rows = ind.reindex(src)[cols].reset_index(drop=True)  # indicadores do frame de origem (causal)
        ind_rows.loc[md["valid"].to_numpy() == 0, :] = np.nan
        block = pd.concat([md.drop(columns=["prev_src_ts"]), ind_rows, *err], axis=1)
        var_col = schema.VAR_OF[kind]
        block[f"{var_col}_var_H"] = indicators.causal_rolling_var(block[var_col], H)
        block["uses_imu"] = bool(meta.get("uses_imu", False))
        df = pd.concat([df, block.add_prefix(f"{m}_")], axis=1)
    return df[list((schema.blind_schema if blind else schema.build_schema)(schema.METHODS))]


def write_outputs(df, sch, out_dir, seq):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    schema.assert_no_leak(sch)
    df.to_parquet(out_dir / f"{seq}.parquet", index=False)
    df.to_csv(out_dir / f"{seq}.csv", index=False)
    (out_dir / "schema.json").write_text(json.dumps(sch, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-dir", required=True)
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="data/output")
    ap.add_argument("--blind", action="store_true", help="modo cego G1: sem gt.tum, sem alvo e sem erros")
    a = ap.parse_args()
    cfg = config.load(a.config)
    df = build_sequence(a.seq_dir, a.runs_dir, cfg.T_L_S, cfg.name, cfg.gt_quality, cfg.max_age_ms, cfg.var_window,
                        a.blind)
    write_outputs(df, (schema.blind_schema if a.blind else schema.build_schema)(schema.METHODS), a.out,
                  Path(a.seq_dir).name)


if __name__ == "__main__":
    main()
