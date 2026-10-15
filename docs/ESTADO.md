# Estado do projeto — 2026-10-15

Branch `feat/dataset-pipeline` (base `master`). Nada rodando. Suíte: 140 testes passando (`scripts/test.sh -q`).

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
- Investigação do KISS-ICP pré-registrada antes de novas execuções (`docs/protocol_kissicp.md`, commit `c1b0b06`).
  Condições D0–D4′, métricas e regra de repetibilidade foram implementadas e validadas somente com dados sintéticos;
  nenhum resultado real novo foi consultado. D3 usa rotação horária, documentada pelos fabricantes, tanto no VLP-16
  quanto no OS1-64. A API do KISS-ICP 1.3.0 não expõe as correspondências do registro; H3 usa o fallback pré-fixado
  de ocupação/PCA, além dos indicadores uniformes já existentes.

## Dados locais (fora do git, em `data/`)
- `data/raw/botanic/1018_00_VLIO.bag` (md5 ok), `GT_pose_qnew/`, `calib_params/`.
- `data/raw/rellis/example/example_filtered.bag`, `poses/` (poses.txt das 5 sequências).
- `data/raw/botanic/1018_13_VLIO.bag` (9,45 GB; GT em `GT_pose_qnew/GT_pose_qnew/gt_1018_13_qnew.bag`).
- `data/raw/rellis/00000/20200213_trail_2.bag` (42,5 GB) + zip original.
- Saídas: `data/output/*.parquet|csv`, `schema.json`, `metrics.csv`; análise da associação em `data/analysis/rellis_assoc/`.

## Próximos passos
1. Fase 1 do KISS-ICP concluída (`docs/RESULTS_kissicp.md`, commit `8564ca1`): 60 execuções, determinístico em
   todas as condições, H4 rejeitada pelo critério operacional; D4′ acionado pela regra. Fase 2 formalmente liberada
   pelo revisor em 2026-10-15 e ainda não iniciada (nenhuma métrica de erro aberta).
2. Fase 2: com a repetição 1 de cada condição (`kissicp_<C>_r1`; r2/r3 não são amostras nem servem para selecionar),
   abrir as métricas pareadas no suporte comum de GT (`ofd.kissicp_analysis`), aplicar literalmente os critérios de
   promoção a D1–D3, usar D4/D4′ só para atribuição diagnóstica, manter o RELLIS exploratório e registrar resultados
   negativos e causas não identificadas sem reinterpretar critérios; documentar Q1/Q2 em `docs/RESULTS_kissicp.md`
   e no relato.
3. Repetir as VOs nas sequências completas (variabilidade entre execuções).
4. Perguntar ao Edvaldo qual representação o modelo consome (ΔT+dt+age ou velocidade se(3)).
5. Push do branch a cada etapa revisada (remoto sincronizado em 2026-10-15).

Decisões e evidências detalhadas: `docs/preflight_rellis.md`, `docs/deskew_rellis.md`, `docs/RESULTS_sequences.md`,
`docs/RELATO_ACADEMICO_PIPELINE.md`, spec e plano em `docs/superpowers/`.
