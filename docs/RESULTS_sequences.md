# Resultados das sequências completas — 2026-10-15

Saídas: `data/output/{1018-13,00000}.parquet|csv`, `data/output/metrics.csv`, `data/output/schema.json`.
Teste de contrato sobre a saída real (`tests/test_pipeline_contract.py`, `max_age_ms` por dataset): passa nas quatro
sequências (1018-00, 1018-13, rellis_example, 00000). Código: commit `2c730a2` + FAST-LIO com
`patches/fastlio/0000-reliable-pointcloud-qos.patch`; casamento pose ↔ scan do FAST-LIO com tolerância de 20 ms (ver
abaixo), remontado do `raw_odom.tum` sem reexecutar o FAST-LIO. Unidades: m, rad→graus. Todos os processos encerrados sem nós órfãos.

Comandos:
```
scripts/run_sequence.sh botanic 1018-13 data/raw/botanic/1018_13_VLIO.bag "" "" \
  data/raw/botanic/GT_pose_qnew/GT_pose_qnew/gt_1018_13_qnew.bag
scripts/run_sequence.sh rellis 00000 data/raw/rellis/00000/20200213_trail_2.bag      # sem GT (veredito C)
```

| seq | method | uses_imu | ate_rmse | rpe_t_frame | rpe_r_frame | rpe_t_10m | rpe_r_10m | coverage | n_failures | n_resets | longest_s | longest_m | eligible_frac |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1018-13 | orbslam3 | False | 1.246 | 0.015 | 0.27° | 0.469 | 0.66° | 74.8% | 2 | 2 | 96.927 | 120.963 | 98.3% |
| 1018-13 | stella | False | 1.601 | 0.017 | 0.27° | 0.586 | 0.68° | 76.4% | 0 | 0 | 100.356 | 122.661 | 99.1% |
| 1018-13 | fastlio | True | 0.067 | 0.016 | 0.39° | 0.100 | 0.80° | 87.6% | 1 | 0 | 183.061 | 200.703 | 99.8% |
| 1018-13 | kissicp | False | 1.827 | 0.033 | 0.33° | 0.250 | 3.06° | 100.0% | 0 | 0 | 208.781 | 201.143 | 100.0% |
| 00000 | orbslam3 | False | — | — | — | — | — | 85.1% | 0 | 0 | 3.500 | — | — |
| 00000 | stella | False | — | — | — | — | — | 85.1% | 0 | 0 | 3.500 | — | — |
| 00000 | fastlio | True | — | — | — | — | — | 99.9% | 0 | 0 | 284.491 | — | — |
| 00000 | kissicp | False | — | — | — | — | — | 100.0% | 0 | 0 | 284.792 | — | — |

Denominadores: `coverage` = passos válidos / passos da grade (scans LiDAR: 2071 no 1018-13, 2849 no 00000);
`eligible_frac` = fração dos passos com GT elegível para RPE.

## BotanicGarden 1018-13 (GT do scanner Leica, `gt_quality: survey`) — confirmatório
- 208,8 s; 2071 scans VLP-16; 1600 pares estéreo (câmeras cobrem ~160 s); 1938 poses de GT, 1936 passos com GT.
- Bag (9,45 GB) íntegro; usa a correção de índice `ofd/bagcompat.py` (cabeçalhos IndexData em duas ordens).
- IMU Xsens cobre os scans 131–1948 (1818); FAST-LIO não estima fora disso (253 scans). Com a tolerância de 20 ms:
  1816/1818 scans cobertos com pose; ausentes só 131–132 (inicialização); a única falha (scan 1949) é a transição no
  fim da cobertura da IMU.
- ORB-SLAM3: 32 quadros sem rastreamento, 2 reinicializações; Stella sem falhas.
- KISS-ICP: ATE 1,83 m em 201 m (no 1018-00: 0,13 m em 115 m), com RPE a 10 m de 0,25 m / 3,06°; maior erro
  rotacional entre os métodos. Causa não investigada.

## RELLIS-3D 00000 — não supervisionado/exploratório (veredito C, `docs/preflight_rellis.md`)
- **Sem GT**: todas as colunas `gt_*` numéricas são NaN (0/2849); ATE/RPE não se aplicam e **não** devem ser calculados
  contra `poses.txt`. A coluna `gt_quality = slam` é só o atributo do dataset.
- 284,9 s; 2849 scans Ouster OS1-64 (intervalos 99,3–100,9 ms); 3068 pares estéreo Nerian (10,77 Hz entregues;
  intervalos de 66,7 ms: 1862, de 133,3 ms: 1205).
- FAST-LIO: 99,89% dos scans com pose (faltam 3 de inicialização); KISS-ICP: 99,96%.
- VOs: rastreamento sem falha (estado `ok` em todos os 3068 quadros), mas cobertura de 85,1% e trecho contínuo máximo
  de 3,5 s. Causa: a grade é a do LiDAR (10 Hz) e, nos intervalos de 133 ms da câmera, alguns passos não recebem quadro
  novo; o passo fica inválido por desenho (`ofd/sync.py`: mesma pose de origem, `i == j`), não por idade (424 passos
  inválidos, todos com `age_ms` ≤ 140). `longest_s` mede, portanto, a continuidade de entrega da câmera, e não
  robustez do rastreamento.

## Tolerância do casamento pose ↔ scan no FAST-LIO (5 → 20 ms)
- Observação: no 1018-13, com 5 ms, os scans 1810–1813 apareciam sem pose (n_failures = 2), de forma idêntica em
  4 execuções (a oficial + `data/runs/1018-13/fastlio_rep{1,2,3}.attempts`). Os dados de entrada desse trecho estão
  íntegros (scans a 100,86 ms; IMU sem lacuna, máx. 2,5 ms) e o log não registra nada.
- Causa: o FAST-LIO **publicou** pose para esses scans, carimbada 5,6–7,0 ms antes de `end_ns`. O carimbo da odometria
  é `lidar_end_time` (`third_party/FAST_LIO/src/laserMapping.cpp:632`) = início do scan + tempo do último ponto que
  sobra após o pré-processamento (distância mínima, subamostragem; `laserMapping.cpp:406`); `end_ns` é o último ponto
  válido da nuvem inteira. São dois conceitos de "fim da varredura"; todos os desvios observados são ≤ 0.
- Correção: `ofd/run_fastlio.py` — `--tol-ms` (padrão 20 ms) e `--reassemble` (remonta do `raw_odom.tum` registrado).
  Justificativa: maior desvio 7,02 ms; poses a ≥ 96,05 ms; casamento monotônico um-para-um; 2 × 20 ms < 96 ms, logo as
  janelas de scans vizinhos não se sobrepõem. A tolerância não foi escolhida pelo ATE (que não mudou).
- `run.json` passa a registrar `tol_ms`, desvio assinado mín./máx./mediano, p95 e máximo absolutos e menor intervalo
  entre poses:

| seq | desvio mín. (ms) | máx. (ms) | mediana (ms) | p95 abs. (ms) | máx. abs. (ms) | menor intervalo entre poses (ms) |
|---|---:|---:|---:|---:|---:|---:|
| 1018-00 | −4,426 | 0,000 | −0,005 | 0,009 | 4,426 | 99,03 |
| 1018-13 | −7,021 | 0,000 | −0,005 | 0,012 | 7,021 | 96,05 |
| rellis_example | −2,197 | 0,000 | 0,000 | 0,000 | 2,197 | 98,98 |
| 00000 | −1,024 | 0,000 | 0,000 | 0,000 | 1,024 | 99,28 |

- Sensibilidade (scans cobertos pela IMU com pose; ausentes):

| seq | 5 ms | 10 ms | 20 ms |
|---|---|---|---|
| 1018-00 | 1141/1143 (122–123) | 1141/1143 (122–123) | 1141/1143 (122–123) |
| 1018-13 | 1812/1818 (131–132, 1810–1813) | 1816/1818 (131–132) | 1816/1818 (131–132) |
| rellis_example | 596/599 (0–2) | 596/599 (0–2) | 596/599 (0–2) |
| 00000 | 2846/2849 (0–2) | 2846/2849 (0–2) | 2846/2849 (0–2) |

- Efeito no 1018-13: cobertura 87,4% → 87,6%, falhas 2 → 1, maior trecho contínuo 169,0 s → 183,1 s; ATE 0,067 m
  inalterado. Demais sequências inalteradas.
