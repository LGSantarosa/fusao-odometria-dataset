# Estado do projeto — 2026-10-14 (fim do dia)

Branch `feat/dataset-pipeline` (base `master`). Nada rodando. Suíte: 110 testes passando (`scripts/test.sh -q`).

## Feito
- Núcleo `ofd/` (Tasks 1–8): SE3, trilhas, sincronização causal, tempo por ponto, indicadores, schema, avaliação.
- Builds reprodutíveis: FAST-LIO (ROS 2, `scripts/build_fastlio.sh`), ORB-SLAM3 e Stella (`scripts/build_*.sh`,
  patches em `patches/`). Runners VO com teste de fumaça sintético.
- Configs geradas da calibração: `python -m tools.make_configs botanic|rellis`.
- Pipeline por sequência: `scripts/run_sequence.sh <ds> <seq> <bag> [start dur] [gt_bag]`.
- Smoke completo: BotanicGarden 1018-00 (com GT) e RELLIS exemplo 60 s (sem GT) → `docs/RESULTS_smoke.md`.
- FAST-LIO validado (3/3 ≥ 90% nos dois datasets) após corrigir nós órfãos, gravador e convenção de tempo.

## Dados locais (fora do git, em `data/`)
- `data/raw/botanic/1018_00_VLIO.bag` (md5 ok), `GT_pose_qnew/`, `calib_params/`.
- `data/raw/rellis/example/example_filtered.bag`, `poses/` (poses.txt das 5 sequências).
- Saídas: `data/output/*.parquet|csv`, `schema.json`, `metrics.csv`.

## Próximos passos
1. Revisão do branch (Codex) — muitas mudanças desde a revisão 2.
2. Baixar BotanicGarden 1018-13 (21 GB; SJTU corta conexões → OneDrive pelo navegador) e RELLIS 00000 (23 GB;
   preflight veredito B: verificar 2847 scans == linhas do poses.txt).
3. Investigar: pulos isolados de 1 scan no FAST-LIO; por que o deskew piora o KISS-ICP.
4. Perguntar ao Edvaldo qual representação o modelo consome (ΔT+dt+age ou velocidade se(3)).

Decisões e evidências detalhadas: `docs/preflight_rellis.md`, `docs/deskew_rellis.md`, spec e plano em
`docs/superpowers/`.
