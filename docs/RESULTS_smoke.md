# Resultados dos smoke tests — 2026-10-14

Saídas: `data/output/{1018-00,rellis_example}.parquet|csv`, `data/output/schema.json`, `data/output/metrics.csv`.
Teste de contrato sobre a saída real (`tests/test_pipeline_contract.py`): passa. Unidades: m, rad→graus.

| seq | method | uses_imu | ate_rmse | rpe_t_frame | rpe_r_frame | rpe_t_10m | rpe_r_10m | coverage | n_failures | n_resets | longest_s | longest_m | eligible_frac |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1018-00 | orbslam3 | False | 0.877 | 0.015 | 0.24° | 0.510 | 0.58° | 65.0% | 0 | 0 | 96.120 | 113.983 | 98.6% |
| 1018-00 | stella | False | 1.135 | 0.016 | 0.24° | 0.625 | 0.60° | 65.0% | 0 | 0 | 96.120 | 113.983 | 98.6% |
| 1018-00 | fastlio | True | 0.047 | 0.016 | 0.31° | 0.082 | 0.55° | 72.3% | 41 | 0 | 8.472 | 12.394 | 99.3% |
| 1018-00 | kissicp | False | 0.132 | 0.024 | 0.22° | 0.195 | 1.73° | 99.9% | 0 | 0 | 147.760 | 115.177 | 100.0% |
| rellis_example | orbslam3 | False | — | — | — | — | — | 83.6% | 0 | 0 | 1.700 | 0.000 | 0.0% |
| rellis_example | stella | False | — | — | — | — | — | 83.6% | 0 | 0 | 1.700 | 0.000 | 0.0% |
| rellis_example | fastlio | True | — | — | — | — | — | 92.5% | 33 | 0 | 7.100 | 0.000 | 0.0% |
| rellis_example | kissicp | False | — | — | — | — | — | 99.8% | 0 | 0 | 59.799 | 0.000 | 0.0% |

## BotanicGarden 1018-00 (GT do scanner Leica, `gt_quality: survey`)
- Tabela: 1466 passos × 121 colunas (84 feature, 13 target, 8 evaluation, 16 metadata); 1299 passos com GT.
- Câmeras só cobrem ~96 s dos 147,8 s → cobertura das VOs 65%. IMU Xsens só cobre +12,3..+127,6 s → FAST-LIO
  não estima fora disso (323 scans).
- FAST-LIO validado: 3 execuções, 97,4% / 98,3% / 96,3% dos scans com IMU, 0 divergências. Restam pulos isolados de
  1 scan (n_failures=41); cada pulo invalida 1 passo (dt=0) — por isso `longest_s` curto apesar do ATE baixo.
- KISS-ICP sem deskew (com deskew o RPE/frame piora de 2,45 para 4,09 cm; ver `docs/deskew_rellis.md`).
- VOs: imagens retificadas na extração (viés vertical médio +0,48 px); ATE ≈ 0,9–1,1 m em 115 m sem loop closure.
- Sanidade vs. paper: os autores avaliaram FAST-LIO2 só com Livox Avia; com VLP16 não há valor de referência direto.

## RELLIS-3D exemplo de 60 s (sem GT — preflight veredito B)
- Métricas de trajetória vazias por desenho; cobertura: VOs 83,6% (câmera Nerian 15 Hz com descartes,
  `max_age_ms=140`), FAST-LIO 92,5% (3 execuções 93,3/92,3/93,0%), KISS-ICP 99,8%.

## Pendências
- RELLIS 00000 (23 GB) liberado pelo veredito B; verificar contagem de scans == 2847 linhas do `poses.txt`.
- BotanicGarden 1018-13 (próxima sequência com GT).
- Causa dos pulos isolados de 1 scan do FAST-LIO; causa do deskew piorar o KISS-ICP.
- Pergunta ao Edvaldo: representação consumida pelo modelo (ΔT+dt+age ou velocidade se(3)) — ambas estão na tabela.
