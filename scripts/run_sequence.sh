#!/usr/bin/env bash
# Pipeline completo de uma sequência.
# uso: scripts/run_sequence.sh <dataset: botanic|rellis> <seq_name> <bag> [start_s duration_s] [gt]
#   gt: bag com o GT, ou um .tum já no frame do LiDAR (RELLIS: gerar com python -m ofd.rellis_gt)
set -euo pipefail
cd "$(dirname "$0")/.."
DS=$1; SEQ=$2; BAG=$3; START=${4:-}; DUR=${5:-}; GT=${6:-}
PY="env -u PYTHONPATH .venv/bin/python"; C=configs/$DS
EXT=data/extracted/$SEQ; RUNS=data/runs/$SEQ
WIN=(); [ -n "$START" ] && WIN+=(--start "$START" --duration "$DUR")
GTA=(); case "$GT" in "") ;; *.tum) GTA+=(--gt-tum "$GT") ;; *) GTA+=(--gt-bag "$GT") ;; esac
mkdir -p "$(dirname "$EXT")" "$RUNS"
$PY -m ofd.extract --bag "$BAG" --config $C/dataset.yaml --out $EXT "${WIN[@]}" "${GTA[@]}" > $EXT.extract.json
$PY -m ofd.run_kissicp --seq-dir $EXT --out $RUNS/kissicp --config $C/dataset.yaml
$PY -m ofd.lidar_indicators --seq-dir $EXT --run-dir $RUNS/kissicp --config $C/dataset.yaml --method kissicp
$PY -m ofd.run_fastlio --bag "$BAG" --config $C/dataset.yaml --fastlio-config $C/fastlio.yaml \
  --seq-dir $EXT --out $RUNS/fastlio "${WIN[@]}"
$PY -m ofd.lidar_indicators --seq-dir $EXT --run-dir $RUNS/fastlio --config $C/dataset.yaml --method fastlio
$PY -m ofd.run_vo --method orbslam3 --seq-dir $EXT --settings $C/orbslam3.yaml --out $RUNS/orbslam3 --rate 1.0
$PY -m ofd.run_vo --method stella --seq-dir $EXT --settings $C/stella.yaml --out $RUNS/stella --rate 1.0
$PY -m ofd.build_dataset --seq-dir $EXT --runs-dir $RUNS --config $C/dataset.yaml --out data/output
$PY -m ofd.evaluate --seq-dir $EXT --runs-dir $RUNS --table data/output/$SEQ.parquet --config $C/dataset.yaml
