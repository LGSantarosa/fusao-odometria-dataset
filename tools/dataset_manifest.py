"""Manifesto reproduzível dos artefatos locais do dataset derivado (`data/output`, fora do git).

Registra, por arquivo, caminho, tamanho, SHA-256 e dimensões; por sequência, linhas, intervalo de `t` e se o CSV
coincide com o Parquet (formato canônico) quando lido com `ofd.schema.CSV_DTYPE`; e a versão do schema (hash,
contagem de papéis, coincidência com `ofd.schema.build_schema`). Sem data/hora: a mesma saída gera o mesmo manifesto.
Os dados brutos e as execuções intermediárias ficam fora.

uso: python -m tools.dataset_manifest [--out docs/dataset_manifest.json]   # gera
     python -m tools.dataset_manifest --check                              # confere data/output contra o manifesto
"""
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from ofd import schema

OUTPUT = Path("data/output")
MANIFEST = Path("docs/dataset_manifest.json")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _shape(path):
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix == ".csv":
        df = pd.read_csv(path, dtype=schema.CSV_DTYPE, low_memory=False)
    else:
        return {}
    return {"rows": len(df), "columns": df.shape[1]}


def csv_matches_parquet(parquet_path, csv_path):
    """Mesmas colunas, linhas e valores. Ponto flutuante com tolerância relativa de 1e-12 (texto do CSV); inteiros
    (timestamps em ns) e booleanos exatos; tipos numéricos diferentes contam como diferença."""
    pq = pd.read_parquet(parquet_path)
    cs = pd.read_csv(csv_path, dtype=schema.CSV_DTYPE, low_memory=False)
    if list(pq.columns) != list(cs.columns) or len(pq) != len(cs):
        return False
    for c in pq.columns:
        a, b = pq[c], cs[c]
        ka, kb = a.dtype.kind, b.dtype.kind
        if ka == kb == "f":
            if not np.allclose(a.to_numpy(), b.to_numpy(), rtol=1e-12, atol=0, equal_nan=True):
                return False
        elif ka in "iub" or kb in "iubf":
            if ka != kb or not np.array_equal(a.to_numpy(), b.to_numpy()):
                return False
        elif not (a.isna().to_numpy() == b.isna().to_numpy()).all() or \
                not (a[a.notna()].astype(str).to_numpy() == b[b.notna()].astype(str).to_numpy()).all():
            return False
    return True


def build_manifest(output_dir, commit):
    output_dir = Path(output_dir)
    files = [{"path": p.name, "bytes": p.stat().st_size, "sha256": _sha256(p), **_shape(p)}
             for p in sorted(output_dir.iterdir()) if p.is_file()]
    sequences = []
    for p in sorted(output_dir.glob("*.parquet")):
        df = pd.read_parquet(p, columns=["t", "seq", "dataset"])
        (seq,), (ds,) = df["seq"].unique(), df["dataset"].unique()
        csv = p.with_suffix(".csv")
        sequences.append({"seq": str(seq), "dataset": str(ds), "rows": len(df),
                          "t_first_ns": int(df["t"].iloc[0]), "t_last_ns": int(df["t"].iloc[-1]),
                          "csv_matches_parquet": csv.exists() and csv_matches_parquet(p, csv)})
    sch = json.loads((output_dir / "schema.json").read_text())
    return {"commit": commit,
            "schema": {"sha256": _sha256(output_dir / "schema.json"), "columns": len(sch),
                       "roles": dict(sorted(Counter(sch.values()).items())),
                       "matches_code": sch == schema.build_schema(schema.METHODS)},
            "sequences": sequences, "files": files}


def dumps(manifest):
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def check(manifest, output_dir):
    """Diferenças entre o manifesto e os arquivos locais; lista vazia = conferem."""
    output_dir = Path(output_dir)
    problems = []
    for f in manifest["files"]:
        p = output_dir / f["path"]
        if not p.exists():
            problems.append(f"{f['path']}: ausente")
        elif p.stat().st_size != f["bytes"] or _sha256(p) != f["sha256"]:
            problems.append(f"{f['path']}: conteúdo diferente do manifesto")
    known = {f["path"] for f in manifest["files"]}
    problems += [f"{p.name}: fora do manifesto" for p in sorted(output_dir.iterdir())
                 if p.is_file() and p.name not in known]
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(MANIFEST))
    ap.add_argument("--check", action="store_true", help="confere data/output contra o manifesto existente")
    a = ap.parse_args()
    if a.check:
        problems = check(json.loads(Path(a.out).read_text()), OUTPUT)
        print("\n".join(problems) or "data/output confere com o manifesto")
        sys.exit(1 if problems else 0)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    Path(a.out).write_text(dumps(build_manifest(OUTPUT, commit)))


if __name__ == "__main__":
    main()
