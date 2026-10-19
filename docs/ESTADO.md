# Estado do projeto — 2026-10-19

Branch `feat/dataset-pipeline` (base `master`). Nada rodando. Suíte: 282 testes passando (`scripts/test.sh -q`).

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
- Saídas: `data/output/*.parquet|csv`, `schema.json`, `metrics.csv` (manifesto em `docs/dataset_manifest.json`);
  análise da associação em `data/analysis/rellis_assoc/`.

## Fechamento do marco do dataset — 19/10/2026

O dataset derivado está concluído no commit `1d9a555` (schema com velocidade em se(3)). Auditoria final em 19/10:

- suíte completa: 236 testes passando com `-W error` (`scripts/test.sh -q -W error`);
- contrato (`ofd.contract.check`, agora com a identidade da sequência) nas quatro sequências reais: 1018-00
  (1466 × 121), 1018-13 (2071 × 121), rellis_example (599 × 121) e 00000 (2849 × 121); o teste do contrato real
  (`tests/test_pipeline_contract.py`) exige exatamente essas quatro, em vez de aceitar o que o glob encontrar;
- **formato canônico: Parquet.** O CSV é cópia de conveniência e deve ser lido com
  `pd.read_csv(..., dtype=ofd.schema.CSV_DTYPE)` (`{"seq": "string"}`): na leitura padrão, o pandas transforma
  `seq` "00000" em 0. Com a leitura tipada, os quatro CSVs coincidem com os Parquets (registrado no manifesto;
  ponto flutuante com tolerância relativa de 1e-12, inteiros — inclusive timestamps em ns — e booleanos exatos);
- `data/output/schema.json` coincide com `ofd.schema.build_schema`: 56 feature, 6 target, 15 evaluation, 44 metadata;
- árvore limpa e `HEAD` = `origin/feat/dataset-pipeline`; `master` (`c0df2b1`) não tem commits próprios.

**Manifesto dos artefatos locais:** `docs/dataset_manifest.json` (versionado; os dados continuam fora do git), gerado
por `python -m tools.dataset_manifest` e conferido com `python -m tools.dataset_manifest --check`. Registra, para os 10
arquivos de `data/output/`, caminho, bytes, SHA-256 e dimensões; por sequência, linhas, intervalo de `t` e a
equivalência CSV × Parquet com a leitura tipada; e a versão do schema (SHA-256, papéis, coincidência com o código). Sem
data/hora: a mesma saída gera o mesmo manifesto. Bags brutos e execuções intermediárias ficam fora (os bags têm md5
registrado na seção acima): o manifesto cobre os artefatos derivados entregáveis, escopo aprovado na revisão de 19/10.

Resultado das frentes do marco:

1. KISS-ICP (`docs/protocol_kissicp.md`, `docs/RESULTS_kissicp.md`, relato §3.7): nenhuma candidata promovida, D0
   (`deskew=False`) mantida. Q1: erro do 1018-13 associado a rotação rápida; Q2 sem causa identificada. Em aberto,
   sem bloquear o dataset: piora do RPE por quadro sob qualquer compensação, inclusive D4 (exige novo protocolo).
2. Repetibilidade das VOs (`docs/protocol_vo_repeat.md`, `docs/RESULTS_vo_repeat.md`): as 8 combinações são variáveis;
   fase 2 sobre r1–r10 com 80/80 execuções válidas (`2480344`). As colunas das VOs no dataset seguem vindo das execuções
   oficiais (seção 8 do protocolo); a variabilidade fica documentada como distribuição.
3. Representação das entradas (`1d9a555`): velocidade em se(3) (`m_vx … m_wz`) com `dt_ms`, `age_ms`, `valid` e
   indicadores como features; alvo `gt_vx … gt_wz`; ΔT como metadata (métodos) e evaluation (GT). Limitação: a divisão
   por dt amplifica ruído com dt pequeno; `dt_ms` como feature permite ao modelo identificá-lo.

**Integração:** fechamento revisado e aprovado em 19/10 (após corrigir a leitura do CSV de 00000 e a comparação exata
de inteiros no manifesto). O commit deste fechamento foi integrado em `master` por fast-forward e marcado com a tag
anotada `dataset-v1.0.0`. **Próxima frente:** pré-registrar o protocolo do modelo de fusão (splits por sequência,
baseline, normalização das 56 features, máscaras de validade, perda sobre `gt_vx … gt_wz`, métricas). Nenhum
treinamento antes desse protocolo.

## Modelo de fusão

Protocolo pré-registrado em 19/10/2026 (`docs/protocol_fusion_model.md`, commit `44bc961`; `master` avançado por
fast-forward até ele). Fase 0 liberada e implementada em 19/10 (`ofd/fusion_{data,models,eval,run}.py`, seção 14 do
protocolo; PyTorch 2.14.1 CPU), validada só com dados sintéticos (45 testes). Nenhum alvo real lido, nada treinado
no dataset. Revisão de 19/10: 7 pontos aceitos, 3 ajustes feitos
(validação não finita = falha; predições do RELLIS gravadas; seleção amarrada à dobra e à sequência de treino).
Fase 0 commitada em `3c34457`.
Fase 1 executada em 19/10 (A: 1 h 24 min; B: 2 h 05 min) e **invalidada**: a padronização não zerava as entradas de
métodos inválidos que no dataset trazem valores antigos (`dt_ms`, `age_ms`, variância móvel), violando a seção 5.
Defeito corrigido com teste; artefatos preservados em `data/analysis/fusion/phase1_invalid_3c34457/`
(`docs/RESULTS_fusion_model.md`). **Próximo passo: revisão da correção e decisão sobre a lacuna das colunas quase
constantes; depois, nova execução da fase 1.** Fase 2 bloqueada.

Decisões e evidências detalhadas: `docs/preflight_rellis.md`, `docs/deskew_rellis.md`, `docs/RESULTS_sequences.md`,
`docs/RELATO_ACADEMICO_PIPELINE.md`, spec e plano em `docs/superpowers/`.
