"""Executor das repetições das VOs — docs/protocol_vo_repeat.md, seção 4.

Uma execução por vez, na ordem intercalada k → sequência → método, com o registro exigido por execução.
uso: python -m ofd.run_vo_repeat --reps 1,2,3
     python -m ofd.run_vo_repeat --reps 4-10 --from-decisions data/analysis/vo_repeat/phase1/decisions.json
     python -m ofd.run_vo_repeat --reps 2 --combos 1018-13/stella --retry-cause "disco cheio"
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

from ofd import run_vo

SEQUENCES = ("1018-00", "1018-13", "rellis_example", "00000")
METHODS = ("orbslam3", "stella")
MAX_REP = 10
LOG_DIR = Path("data/analysis/vo_repeat/logs")
PATCHES = Path(__file__).resolve().parents[1] / "patches"


def plan(reps, combos):
    """Ordem fixa da seção 4 sobre pares exatos (sequência, método): repetição, sequência, método."""
    combos = [tuple(c) for c in combos]
    if len(set(combos)) != len(combos):
        raise ValueError(f"combinações repetidas: {combos}")
    combos = set(combos)
    unknown = {c for c in combos if c[0] not in SEQUENCES or c[1] not in METHODS}
    if unknown:
        raise ValueError(f"combinações desconhecidas: {sorted(unknown)}")
    return [(k, s, m) for k in sorted(reps) for s in SEQUENCES for m in METHODS if (s, m) in combos]


def parse_combos(text):
    """'all' ou 'seq/método,seq/método'; rejeita nomes desconhecidos."""
    if text == "all":
        return [(s, m) for s in SEQUENCES for m in METHODS]
    combos = []
    for item in text.split(","):
        seq, sep, method = item.partition("/")
        if not sep or seq not in SEQUENCES or method not in METHODS:
            raise ValueError(f"combinação desconhecida: {item!r}")
        if (seq, method) in combos:
            raise ValueError(f"combinação repetida: {item!r}")
        combos.append((seq, method))
    return combos


def parse_reps(text):
    """'1,2,3' ou '4-10'; índices de 1 a 10, sem repetição."""
    reps = []
    for item in text.split(","):
        lo, sep, hi = item.partition("-")
        if not lo.isdigit() or (sep and not hi.isdigit()):
            raise ValueError(f"repetição inválida: {item!r}")
        reps.extend(range(int(lo), int(hi) + 1) if sep else [int(lo)])
    if not reps or len(set(reps)) != len(reps) or min(reps) < 1 or max(reps) > MAX_REP:
        raise ValueError(f"repetições inválidas: {text!r}")
    return reps


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _loadavg():
    return Path("/proc/loadavg").read_text().split()[:3]


def _cpu_model():
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


def _repo_commit():
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or None


def _attempt_path(path, n):
    path = Path(path)
    return path.with_name(f"{path.stem}.attempt{n}{path.suffix}") if path.suffix else \
        path.with_name(f"{path.name}.attempt{n}")


def _write_json_atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, path)


def _archive(paths):
    """Arquiva a tentativa existente (diretório, registro e log) sob o mesmo k.

    O número arquivado é o menor n livre para os três caminhos, de modo que um registro ilegível ou uma tentativa
    interrompida não perdem nem reutilizam um número. Devolve (número da nova tentativa, tentativas anteriores).
    """
    n = 1
    while any(_attempt_path(p, n).exists() for p in paths.values() if p is not None):
        n += 1
    previous = []
    record = paths["record"]
    try:
        rec = json.loads(Path(record).read_text()) if Path(record).exists() else {}
        previous = list(rec.get("previous_attempts", [])) if isinstance(rec, dict) else []
        unreadable = not isinstance(rec, dict)
    except (ValueError, OSError):
        unreadable = True
    entry = {"attempt": n}
    if unreadable:
        entry["record_unreadable"] = True
    for key, path in paths.items():
        if path is not None and Path(path).exists():
            target = _attempt_path(path, n)
            shutil.move(str(path), str(target))
            entry[key] = str(target)
    return n + 1, previous + [entry]


def execute(cmd, out_dir, files, seq_duration_s, record_path, log_path=None, method=None, retry_cause=None):
    """Executa uma repetição e grava o registro.

    Nunca sobrescreve: diretório, registro ou log existentes contam como tentativa anterior, e só se prossegue com
    `retry_cause` (causa externa documentada, seção 4, item 6); a tentativa anterior é arquivada com o sufixo
    `.attempt<n>` e o mesmo k é mantido. O registro é gravado atomicamente antes do subprocesso (`status: running`)
    e atualizado atomicamente no fim (`status: finished`), de modo que uma interrupção deixa a tentativa registrada.
    """
    paths = {"out_dir": Path(out_dir), "record": Path(record_path),
             "log": Path(log_path) if log_path is not None else None}
    existing = any(p is not None and p.exists() for p in paths.values())
    if existing and not retry_cause:
        raise FileExistsError(f"tentativa já existe para {out_dir}; nova tentativa exige retry_cause")
    if retry_cause and not existing:
        raise ValueError("retry_cause sem tentativa anterior")
    attempt, previous = _archive(paths) if existing else (1, [])
    rec = {"cmd": [str(c) for c in cmd], "out_dir": str(out_dir), "attempt": attempt, "status": "running",
           "exit_code": None, "retry_cause": retry_cause, "previous_attempts": previous,
           "repo_commit": _repo_commit(), "method": method,
           "method_commit": run_vo.COMMIT.get(method),
           "method_patches": ({p.name: _sha256(p) for p in sorted((PATCHES / method).glob("*.patch"))}
                              if method else {}),
           "cpu_model": _cpu_model(), "n_cpus": os.cpu_count(),
           **{f"sha256_{name}": _sha256(path) for name, path in files.items()},
           "loadavg_start": _loadavg(), "start_unix": time.time()}
    _write_json_atomic(record_path, rec)
    t0 = time.monotonic()
    if log_path is not None:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as log:
            code = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    else:
        code = subprocess.run(cmd, capture_output=True).returncode
    wall = time.monotonic() - t0
    rec.update(status="finished", exit_code=int(code), wall_s=wall, seq_duration_s=float(seq_duration_s),
               wall_over_sequence=wall / seq_duration_s, loadavg_end=_loadavg())
    _write_json_atomic(record_path, rec)
    return rec


def dataset_of(seq):
    return "botanic" if seq.startswith("1018-") else "rellis"


def main():
    ap = argparse.ArgumentParser(description="Repetições das VOs (protocolo pré-registrado)")
    ap.add_argument("--reps", required=True, help="ex.: 1,2,3 ou 4-10")
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--combos", default="all", help="all ou seq/método,seq/método")
    sel.add_argument("--from-decisions", help="decisions.json da fase 1: só as combinações variáveis")
    ap.add_argument("--retry-cause", help="causa externa documentada; exige exatamente uma execução")
    a = ap.parse_args()
    if a.from_decisions:
        decisions = json.loads(Path(a.from_decisions).read_text())
        combos = [tuple(key.split("/")) for key, d in decisions.items() if d == "variable"]
    else:
        combos = parse_combos(a.combos)
    jobs = plan(parse_reps(a.reps), combos)
    if not jobs:
        ap.error("nenhuma execução selecionada")
    if a.retry_cause and len(jobs) != 1:
        ap.error("--retry-cause exige exatamente uma execução (uma combinação e uma repetição)")
    for k, seq, method in jobs:
        seq_dir = Path("data/extracted") / seq
        settings = Path("configs") / dataset_of(seq) / f"{method}.yaml"
        stamps = pd.read_csv(seq_dir / "images" / "stamps.csv")["ts_ns"]
        out = Path("data/runs") / seq / f"{method}_r{k}"
        name = f"{seq}_{method}_r{k}"
        rec = execute([sys.executable, "-m", "ofd.run_vo", "--method", method, "--seq-dir", seq_dir,
                       "--settings", settings, "--out", out, "--rate", "1.0"],
                      out,
                      {"bin": run_vo.BIN[method], "vocab": run_vo.VOCAB[method], "settings": settings,
                       "extract": Path("data/extracted") / f"{seq}.extract.json"},
                      seq_duration_s=(stamps.max() - stamps.min()) / 1e9,
                      record_path=LOG_DIR / f"{name}.json", log_path=LOG_DIR / f"{name}.log",
                      method=method, retry_cause=a.retry_cause)
        print(f"{'ok' if rec['exit_code'] == 0 else 'FAIL'} {name} exit={rec['exit_code']} "
              f"attempt={rec['attempt']} wall={rec['wall_s']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
