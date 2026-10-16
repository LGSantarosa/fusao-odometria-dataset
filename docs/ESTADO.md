# Estado do projeto — 2026-10-16

Branch `feat/dataset-pipeline` (base `master`). Nada rodando. Suíte: 211 testes passando (`scripts/test.sh -q`).

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
1. Investigação do KISS-ICP concluída (fases 1 e 2; `docs/RESULTS_kissicp.md`, relato §3.7). Fase 2 (16/10, só r1,
   métricas pareadas no suporte comum de GT, `tools/kissicp_phase2.py`): **nenhuma candidata promovida, D0 mantida**
   (D1/D3 passam no 1018-13 e falham no RPE do 1018-00). Q1: erro do 1018-13 associado a trechos de rotação rápida;
   H3 inconclusiva/não atribuída (proxies de estrutura mistos). Q2: causa não identificada (H2, H4, H6 não sustentadas; H1 não atribuída
   pelo teste pré-registrado; H5 parcial). Em aberto: piora do RPE por quadro sob qualquer compensação, inclusive D4.
2. Repetições das VOs: protocolo pré-registrado (`docs/protocol_vo_repeat.md`, commit `e682f15`); implementação
   validada só com dados sintéticos (`ofd/vo_repeat.py`, `ofd/run_vo_repeat.py`, commit `084243d`). Fase 1 (r1–r3,
   `docs/RESULTS_vo_repeat.md`): 24/24 válidas; as 8 combinações são variáveis. Escalonamento r4–r10 concluído em
   16/10: 56/56 ok, 80/80 válidas; as 8 combinações seguem variáveis com dez execuções (análise em
   `data/analysis/vo_repeat/phase1_escalated`; A diverge só no ORB-SLAM3 em 1018-13 e 00000). **Próximo passo: revisão
   do escalonamento (commitado sem revisão externa, a pedido do usuário) e liberação da fase 2** (métricas de erro como
   distribuição sobre r1–r10, seção 7 do protocolo). Fase 2 e métricas de erro bloqueadas até essa liberação.
3. Perguntar ao Edvaldo qual representação o modelo consome (ΔT+dt+age ou velocidade se(3)).
4. Push do branch a cada etapa revisada (remoto sincronizado em 2026-10-16).

Decisões e evidências detalhadas: `docs/preflight_rellis.md`, `docs/deskew_rellis.md`, `docs/RESULTS_sequences.md`,
`docs/RELATO_ACADEMICO_PIPELINE.md`, spec e plano em `docs/superpowers/`.
