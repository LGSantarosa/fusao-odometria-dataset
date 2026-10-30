#!/usr/bin/env bash
# Job cego G1 de uma sequência (docs/PLAN_model_comparison.md, seção G1, passos 3–4): extração sem o tópico de GT,
# odometrias e tabela só com metadados e features. Não aceita GT, não roda ofd.evaluate e não imprime métricas.
# uso: scripts/run_sequence_blind.sh <dataset> <seq_name> <bag> [start_s duration_s]
#   saídas: $BLIND_ROOT/{extracted,runs,tables}/ (padrão data/blind)
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -eq 3 ] || [ $# -eq 5 ] || { echo "uso: $0 <dataset> <seq> <bag> [start_s duration_s]" >&2; exit 2; }
DS=$1; SEQ=$2; BAG=$3; START=${4:-}; DUR=${5:-}
PY="env -u PYTHONPATH .venv/bin/python"; C=configs/$DS
ROOT=${BLIND_ROOT:-data/blind}
EXT=$ROOT/extracted/$SEQ; RUNS=$ROOT/runs/$SEQ
WIN=(); [ -n "$START" ] && WIN+=(--start "$START" --duration "$DUR")
if [ -e "$EXT" ] || [ -e "$RUNS" ]; then echo "$EXT ou $RUNS já existe; o job cego roda uma única vez" >&2; exit 1; fi
mkdir -p "$(dirname "$EXT")" "$RUNS"
$PY -m ofd.extract --blind --bag "$BAG" --config $C/dataset.yaml --out $EXT "${WIN[@]}" > $EXT.extract.json
$PY -m ofd.run_kissicp --seq-dir $EXT --out $RUNS/kissicp --config $C/dataset.yaml
$PY -m ofd.lidar_indicators --seq-dir $EXT --run-dir $RUNS/kissicp --config $C/dataset.yaml --method kissicp
$PY -m ofd.run_fastlio --bag "$BAG" --config $C/dataset.yaml --fastlio-config $C/fastlio.yaml \
  --seq-dir $EXT --out $RUNS/fastlio "${WIN[@]}"
$PY -m ofd.lidar_indicators --seq-dir $EXT --run-dir $RUNS/fastlio --config $C/dataset.yaml --method fastlio
$PY -m ofd.run_vo --method orbslam3 --seq-dir $EXT --settings $C/orbslam3.yaml --out $RUNS/orbslam3 --rate 1.0
$PY -m ofd.run_vo --method stella --seq-dir $EXT --settings $C/stella.yaml --out $RUNS/stella --rate 1.0
$PY -m ofd.build_dataset --blind --seq-dir $EXT --runs-dir $RUNS --config $C/dataset.yaml --out $ROOT/tables
