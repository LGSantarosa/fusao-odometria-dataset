"""Modo cego G1 — passos 3 a 6 de docs/PLAN_model_comparison.md (seção G1).

A extração e a tabela cegas ficam em `ofd.extract --blind` e `ofd.build_dataset --blind`
(`scripts/run_sequence_blind.sh`). Este módulo cobre o que vem depois:

- `freeze-features`: manifesto das tabelas cegas, runs, configuração, protocolo, ambiente e commit;
- `predict`: predições dos modelos congelados a partir das tabelas verificadas, com manifesto próprio;
- `unlock`: abertura única — verifica os dois manifestos, deslacra cada GT só durante a leitura, anexa o GT sem tocar
  nas features e calcula as métricas.

Nada antes de `unlock` lê GT ou produz alvo, erro ou métrica. A abertura verifica commit e manifestos e só então cria
`UNLOCK_STARTED`, antes da primeira leitura de GT: uma falha depois disso não permite nova tentativa no mesmo
diretório.

    python -m ofd.blind freeze-features --seq <seq> <tabela.parquet> <runs_dir> [--seq ...] --config <yaml>
        --protocol <md> --out <feature_manifest.json>
    python -m ofd.blind predict --features <feature_manifest.json> --model B5 [--model ...] --out-dir <dir>
    python -m ofd.blind unlock --features <feature_manifest.json> --predictions <prediction_manifest.json>
        --acquisition-dir <dir> --out-dir <dir>
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import config, evaluate, extract, fusion_data, fusion_eval, schema, sync, tracks
from ofd.g0_triage import _custody, _git

VERSION = 1
ENV_FILES = ("requirements.lock", "pyproject.toml")
PRED = [f"pred_{c}" for c in schema.TW]


class BlindError(Exception):
    """Violação do fluxo cego (hash divergente, árvore suja, abertura repetida); nada é calculado."""


# ---------------------------------------------------------------- hashes

def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def logical_sha256(df):
    """Hash do conteúdo lógico (nomes, ordem, tipos numéricos e valores), independente da codificação do arquivo."""
    h = hashlib.sha256()
    for c in df.columns:
        a = df[c].to_numpy()
        if a.dtype.kind in "biuf":
            if a.dtype.kind == "f":
                a = np.where(np.isnan(a), np.nan, a)  # NaN canônico
            h.update(json.dumps([c, a.dtype.str]).encode())
            h.update(np.ascontiguousarray(a, dtype=a.dtype.newbyteorder("<")).tobytes())
        else:
            h.update(json.dumps([c, "str", [None if pd.isna(v) else str(v) for v in a]]).encode())
    return h.hexdigest()


def _entry(path):
    path = Path(path)
    e = {"path": str(path), "bytes": path.stat().st_size, "sha256": file_sha256(path)}
    if path.suffix == ".parquet":
        e["logical_sha256"] = logical_sha256(pd.read_parquet(path))
    return e


def _files(path):
    path = Path(path)
    return sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]


def _commit(require_clean):
    if require_clean and _git("status", "--porcelain"):
        raise BlindError("árvore git suja: o fluxo cego exige commit limpo")
    return _git("rev-parse", "HEAD")


def _write_manifest(kind, out, require_clean, **body):
    out = Path(out)
    if out.exists():
        raise BlindError(f"{out} já existe; manifestos não são sobrescritos")
    m = {"kind": kind, "blind_version": VERSION, "commit": _commit(require_clean),
         "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
         "environment": [_entry(p) for p in ENV_FILES if Path(p).is_file()], **body}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, indent=2) + "\n")
    return m


def _entries(m):
    yield from m["environment"]
    for s in m.get("sequences", {}).values():
        yield s["table"]
        yield from s.get("runs", [])
    for k in ("config", "protocol"):
        if k in m:
            yield m[k]
    yield from m.get("models", [])
    yield from m.get("predictions", {}).values()


def verify_manifest(path, kind):
    """Recalcula todos os hashes do manifesto; qualquer divergência levanta BlindError."""
    m = json.loads(Path(path).read_text())
    if m.get("kind") != kind:
        raise BlindError(f"{path}: manifesto do tipo {m.get('kind')!r}, esperado {kind!r}")
    bad = []
    for e in _entries(m):
        p = Path(e["path"])
        if not p.is_file() or _entry(p) != e:
            bad.append(str(p))
    if bad:
        raise BlindError(f"{path}: arquivos ausentes ou alterados: {bad}")
    return m


# ---------------------------------------------------------------- passo 5a: congelamento das features

def freeze_features(seqs, config_path, protocol_path, out, require_clean=True):
    """seqs: {seq: (tabela cega .parquet, diretório de runs)}. Confere o schema cego antes de registrar."""
    blind_cols = list(schema.blind_schema(schema.METHODS))
    body = {}
    for seq, (table, runs) in sorted(seqs.items()):
        df = pd.read_parquet(table)
        if list(df.columns) != blind_cols:
            raise BlindError(f"{table}: colunas diferentes do schema cego")
        if not (df["seq"].astype(str) == seq).all():
            raise BlindError(f"{table}: seq diferente de {seq!r}")
        body[seq] = {"table": _entry(table), "runs_dir": str(runs),
                     "runs": [_entry(p) for m in schema.METHODS for p in _files(Path(runs) / m)]}
    return _write_manifest("features", out, require_clean, sequences=body, config=_entry(config_path),
                           protocol=_entry(protocol_path))


# ---------------------------------------------------------------- passo 4: predição cega

def b5_mean(df):
    """B5: média das fontes válidas no passo; NaN quando nenhuma é válida. Não exige treino."""
    tw, valid = fusion_data.method_twists(df)
    out = np.full((len(df), len(schema.TW)), np.nan)
    any_valid = valid.any(axis=1)
    out[any_valid] = np.nanmean(tw[any_valid], axis=1)
    return out


# Modelos treinados entram aqui quando forem congelados (fases 1–3), com seus artefatos listados em `models`.
PREDICTORS = {"B5": b5_mean}


def predict(feature_manifest, models, out_dir, require_clean=True):
    fm = verify_manifest(feature_manifest, "features")
    out_dir = Path(out_dir)
    preds = {}
    for seq, s in fm["sequences"].items():
        df = pd.read_parquet(s["table"]["path"])
        res = pd.DataFrame({"t": df["t"], "seq": df["seq"]})
        for name in models:
            p = np.asarray(PREDICTORS[name](df[fusion_data.FEATURES + ["t", "seq"]]), float)
            if p.shape != (len(df), len(schema.TW)):
                raise BlindError(f"{name}: predição com forma {p.shape}")
            for j, c in enumerate(PRED):
                res[f"{name}_{c}"] = p[:, j]
        path = out_dir / "predictions" / f"{seq}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        res.to_parquet(path, index=False)
        preds[seq] = _entry(path)
    return _write_manifest("predictions", out_dir / "prediction_manifest.json", require_clean,
                           feature_manifest=_entry(feature_manifest), model_names=list(models), models=[],
                           predictions=preds)


# ---------------------------------------------------------------- passo 6: abertura única

def _read_gt(gt, expected_sha, topic, seq, commit):
    """Deslacra só durante a leitura (como a triagem), confere o sha256 registrado e relacra."""
    sealed = not os.access(gt, os.R_OK)
    if sealed:
        _custody(gt, "unlock_read", seq, commit, by="ofd.blind")
        os.chmod(gt, 0o400)
    try:
        sha = file_sha256(gt)
        if sha != expected_sha:
            raise BlindError(f"{gt}: sha256 {sha} difere do registrado {expected_sha}")
        ts, Ts, dropped = extract.gt_from_bag(gt, topic)
    finally:
        if sealed:
            os.chmod(gt, 0o000)
            _custody(gt, "reseal", seq, commit, by="ofd.blind")
    return ts, Ts, dropped, sha


def _expected_gt_sha(acq, triage_dir, seq):
    if "sha256" in acq["gt"]:
        return acq["gt"]["sha256"].lower()
    tri = Path(triage_dir) / f"{seq}.json"
    if tri.is_file():
        return json.loads(tri.read_text())["hashes"]["gt"]["sha256"]
    raise BlindError(f"{seq}: sem sha256 registrado do GT (manifesto de aquisição ou triagem)")


def evaluation_table(table, runs_dir, cfg, gt_ts, gt_Ts):
    """t + gt_* + <método>_err_*, recalculados dos runs congelados no grid da tabela cega."""
    grid = table["t"].to_numpy(np.int64)
    ev = pd.concat([table[["t"]].reset_index(drop=True), sync.gt_deltas(gt_ts, gt_Ts, grid)], axis=1)
    for m in schema.METHODS:
        track, _, _ = tracks.load_run(Path(runs_dir) / m)
        md = sync.method_deltas(track, grid, cfg.T_L_S[m], cfg.max_age_ms)
        same = md[["valid", "src_ts"]].reset_index(drop=True).equals(
            table[[f"{m}_valid", f"{m}_src_ts"]].reset_index(drop=True).set_axis(["valid", "src_ts"], axis=1))
        if not same:
            raise BlindError(f"{m}: runs não reproduzem a tabela congelada")
        err = sync.method_errors(md, track, cfg.T_L_S[m], gt_ts, gt_Ts)
        ev[f"{m}_err_t"], ev[f"{m}_err_r"] = err["err_t"].to_numpy(), err["err_r"].to_numpy()
    return ev


def prediction_metrics(seq, pred, ev, models):
    y = ev[[f"gt_{c}" for c in schema.TW]].to_numpy(float)
    rows = []
    for name in models:
        p = pred[[f"{name}_{c}" for c in PRED]].to_numpy(float)
        target = np.isfinite(y).all(axis=1)
        ok = target & np.isfinite(p).all(axis=1)
        rows.append({"seq": seq, "model": name, "n_target": int(target.sum()), "n_pred_missing": int((target & ~ok).sum()),
                     **fusion_eval.primary(p[ok], y[ok])})
    return rows


def unlock(feature_manifest, prediction_manifest, acquisition_dir, out_dir, triage_dir=None, require_clean=True):
    out_dir = Path(out_dir)
    if (out_dir / "UNLOCK_STARTED").exists():
        raise BlindError(f"abertura já iniciada em {out_dir}; não há segunda tentativa")
    # verificações sem GT: uma divergência aqui impede a abertura sem consumi-la
    commit = _commit(require_clean)
    fm = verify_manifest(feature_manifest, "features")
    pm = verify_manifest(prediction_manifest, "predictions")
    if pm["feature_manifest"] != _entry(feature_manifest):
        raise BlindError("manifesto de predições não corresponde ao manifesto de features")
    if set(pm["predictions"]) != set(fm["sequences"]):
        raise BlindError("predições e features cobrem sequências diferentes")
    cfg = config.load(fm["config"]["path"])
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(out_dir / "UNLOCK_STARTED", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise BlindError(f"abertura já iniciada em {out_dir}; não há segunda tentativa") from None
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    os.write(fd, json.dumps({"at": started, "commit": commit}).encode())
    os.close(fd)
    gts, src_rows, pred_rows, outputs = {}, [], [], {}
    for seq, s in fm["sequences"].items():
        acq = json.loads((Path(acquisition_dir) / f"{seq}.json").read_text())
        if acq["seq"] != seq:
            raise BlindError(f"{seq}: manifesto de aquisição de {acq['seq']}")
        gt_ts, gt_Ts, dropped, sha = _read_gt(Path(acq["gt"]["path"]), _expected_gt_sha(acq, triage_dir, seq),
                                              cfg.topics.get("gt", "/gt_poses"), seq, commit)
        gts[seq] = {"path": acq["gt"]["path"], "sha256": sha, "dropped_nonfinite": dropped}
        table = pd.read_parquet(s["table"]["path"])
        ev = evaluation_table(table, s["runs_dir"], cfg, gt_ts, gt_Ts)
        ev_path = out_dir / "evaluation" / f"{seq}.parquet"
        ev_path.parent.mkdir(parents=True, exist_ok=True)
        ev.to_parquet(ev_path, index=False)
        full = pd.concat([table.reset_index(drop=True), ev.drop(columns=["t"])], axis=1)
        full = full[list(schema.build_schema(schema.METHODS))]
        src_rows.append(evaluate.evaluate_methods(seq, s["runs_dir"], full, cfg.T_L_S, gt_ts, gt_Ts))
        pred = pd.read_parquet(pm["predictions"][seq]["path"])
        if not pred["t"].equals(table["t"]):
            raise BlindError(f"{seq}: predições fora do grid da tabela")
        pred_rows += prediction_metrics(seq, pred, ev, pm["model_names"])
        # anexar o GT não pode alterar as features congeladas
        if _entry(s["table"]["path"]) != s["table"]:
            raise BlindError(f"{seq}: tabela de features alterada durante a abertura")
        outputs[seq] = _entry(ev_path)
    pd.concat(src_rows).to_csv(out_dir / "source_metrics.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(out_dir / "prediction_metrics.csv", index=False)
    um = {"kind": "unlock", "blind_version": VERSION, "commit": commit, "started_at": started,
          "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
          "feature_manifest": _entry(feature_manifest), "prediction_manifest": _entry(prediction_manifest),
          "gt": gts, "evaluation": outputs,
          "metrics": [_entry(out_dir / "source_metrics.csv"), _entry(out_dir / "prediction_metrics.csv")]}
    (out_dir / "unlock_manifest.json").write_text(json.dumps(um, indent=2) + "\n")
    return um


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze-features")
    f.add_argument("--seq", nargs=3, action="append", required=True, metavar=("SEQ", "TABLE", "RUNS"))
    f.add_argument("--config", required=True)
    f.add_argument("--protocol", required=True)
    f.add_argument("--out", required=True)
    p = sub.add_parser("predict")
    p.add_argument("--features", required=True)
    p.add_argument("--model", action="append", required=True, choices=sorted(PREDICTORS))
    p.add_argument("--out-dir", required=True)
    u = sub.add_parser("unlock")
    u.add_argument("--features", required=True)
    u.add_argument("--predictions", required=True)
    u.add_argument("--acquisition-dir", required=True)
    u.add_argument("--triage-dir")
    u.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    if a.cmd == "freeze-features":
        freeze_features({s: (t, r) for s, t, r in a.seq}, a.config, a.protocol, a.out)
        print(f"{a.out} gravado")
    elif a.cmd == "predict":
        predict(a.features, a.model, a.out_dir)
        print(f"{Path(a.out_dir) / 'prediction_manifest.json'} gravado")
    else:
        um = unlock(a.features, a.predictions, a.acquisition_dir, a.out_dir, a.triage_dir)
        print(f"abertura concluída: {Path(a.out_dir) / 'unlock_manifest.json'} ({len(um['gt'])} sequências)")


if __name__ == "__main__":
    main()
