# Estado do projeto — 2026-10-15

Branch `feat/dataset-pipeline` (base `master`). Nada rodando. Suíte: 115 testes passando (`scripts/test.sh -q`).

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

## Dados locais (fora do git, em `data/`)
- `data/raw/botanic/1018_00_VLIO.bag` (md5 ok), `GT_pose_qnew/`, `calib_params/`.
- `data/raw/rellis/example/example_filtered.bag`, `poses/` (poses.txt das 5 sequências).
- Saídas: `data/output/*.parquet|csv`, `schema.json`, `metrics.csv`.

## Próximos passos
1. Baixar BotanicGarden 1018-13 (21 GB; SJTU corta conexões → OneDrive pelo navegador) e RELLIS 00000 (23 GB;
   preflight veredito B: `ofd.rellis_gt` já recusa se scans != 2847 linhas do poses.txt). Confirmar com o FAST-LIO
   que a pose da linha k vale no stamp do header do scan k (início do scan).
2. Investigar por que o deskew piora o KISS-ICP.
3. Perguntar ao Edvaldo qual representação o modelo consome (ΔT+dt+age ou velocidade se(3)).

Decisões e evidências detalhadas: `docs/preflight_rellis.md`, `docs/deskew_rellis.md`, spec e plano em
`docs/superpowers/`.
