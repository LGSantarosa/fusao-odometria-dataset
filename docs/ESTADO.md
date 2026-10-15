# Estado do projeto — 2026-10-15

Branch `feat/dataset-pipeline` (base `master`). Nada rodando. Suíte: 131 testes passando (`scripts/test.sh -q`).

## Feito
- Núcleo `ofd/` (Tasks 1–8): SE3, trilhas, sincronização causal, tempo por ponto, indicadores, schema, avaliação.
- Builds reprodutíveis: FAST-LIO (ROS 2, `scripts/build_fastlio.sh`), ORB-SLAM3 e Stella (`scripts/build_*.sh`,
  patches em `patches/`). Runners VO com teste de fumaça sintético.
- Configs geradas da calibração: `python -m tools.make_configs botanic|rellis`.
- Pipeline por sequência: `scripts/run_sequence.sh <ds> <seq> <bag> [start dur] [gt: bag ou .tum]`.
- Smoke completo: BotanicGarden 1018-00 (com GT) e RELLIS exemplo 60 s (sem GT) → `docs/RESULTS_smoke.md`.
- FAST-LIO validado (3/3 nos dois datasets; só faltam os scans de inicialização) após corrigir nós órfãos, gravador,
  convenção de tempo e a perda de nuvens no QoS best-effort (patch versionado em `patches/fastlio/`; o FAST_LIO agora
  é um clone fixado em `third_party/FAST_LIO`, não mais o checkout do robô).
- Revisão Codex do branch atendida (7db3804): GT do RELLIS por índice (`python -m ofd.rellis_gt`), `run_sequence.sh`
  aceita `.tum` como GT, cobertura da IMU no `ok` do FAST-LIO, `max_age_ms` por dataset no contrato, `verify_pin`
  nos builds.
- Sequências completas processadas (`docs/RESULTS_sequences.md`): BotanicGarden 1018-13 com GT (confirmatório) e
  RELLIS 00000 sem GT (exploratório). Contrato passa nas 4 sequências.
- RELLIS 00000: associação poses.txt ↔ scans investigada (`tools/rellis_assoc.py`); **veredito C definitivo** — sem GT,
  sem ATE/RPE contra `poses.txt`; `ofd.rellis_gt` continua recusando (`docs/preflight_rellis.md`).
- FAST-LIO: casamento pose ↔ scan com tolerância de 20 ms (`--tol-ms`; desvio registrado no `run.json`); `--reassemble`
  remonta do `raw_odom.tum` sem reexecutar.

## Dados locais (fora do git, em `data/`)
- `data/raw/botanic/1018_00_VLIO.bag` (md5 ok), `GT_pose_qnew/`, `calib_params/`.
- `data/raw/rellis/example/example_filtered.bag`, `poses/` (poses.txt das 5 sequências).
- `data/raw/botanic/1018_13_VLIO.bag` (9,45 GB; GT em `GT_pose_qnew/GT_pose_qnew/gt_1018_13_qnew.bag`).
- `data/raw/rellis/00000/20200213_trail_2.bag` (42,5 GB) + zip original.
- Saídas: `data/output/*.parquet|csv`, `schema.json`, `metrics.csv`; análise da associação em `data/analysis/rellis_assoc/`.

## Próximos passos
1. Investigar o ATE do KISS-ICP no 1018-13 (1,83 m vs. 0,13 m no 1018-00) e por que o deskew piora o KISS-ICP.
2. Repetir VOs e KISS-ICP nas sequências completas (variabilidade entre execuções).
3. Perguntar ao Edvaldo qual representação o modelo consome (ΔT+dt+age ou velocidade se(3)).
4. Push do branch quando os pipelines estiverem consolidados (commits locais à frente do remoto).

Decisões e evidências detalhadas: `docs/preflight_rellis.md`, `docs/deskew_rellis.md`, `docs/RESULTS_sequences.md`,
`docs/RELATO_ACADEMICO_PIPELINE.md`, spec e plano em `docs/superpowers/`.
