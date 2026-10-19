# Resultados — variabilidade entre execuções das VOs (protocolo `docs/protocol_vo_repeat.md`)

## Fase 1 — repetibilidade, decidida antes de abrir métricas de erro — 16/10/2026

Código: `084243d` (protocolo `e682f15`). Execuções: `python -m ofd.run_vo_repeat --reps 1,2,3` (24 execuções, uma por
vez, ordem intercalada da seção 4, `--rate 1.0`), em `data/runs/<seq>/<método>_r<k>`; registros e logs em
`data/analysis/vo_repeat/logs/` (`phase1_driver.log` e `<seq>_<método>_r<k>.{json,log}`). Análise:
`python -m ofd.vo_repeat --out data/analysis/vo_repeat/phase1` (`decisions.json`, `<seq>_<método>_{runs,pairs}.csv`).
Nenhuma métrica de erro (GT) foi calculada ou consultada.

**Execução.** 24/24 com código de saída 0, `status: finished`, tentativa 1, e válidas pela seção 5.1. Razão entre a
duração de relógio e a da sequência: 1,02 a 1,14, exceto a primeira execução da fase (1018-00/ORB-SLAM3 r1: 1,32;
r2 e r3: 1,07 e 1,08). Carga média de 1 min no início das execuções: 0,90 a 5,94 (16 núcleos), sem outro experimento
em paralelo; houve uso interativo da máquina (navegador) durante a fase.

**Hashes distintos entre as 3 execuções.** `poses_causal.tum` e `indicators.csv`: 3 em todas as combinações.
`state.csv`: 1 em todas, exceto 00000/ORB-SLAM3 (2).

**Componentes A, B e C** (máximo sobre os 3 pares; B e C no frame `cam_left`, sem GT):

| Combinação | A idêntico nos 3 pares | B máx. t (m) | B máx. r (°) | C máx. t (m) | C máx. r (°) | Decisão |
|---|---|---:|---:|---:|---:|---|
| 1018-00 / ORB-SLAM3 | sim | 0,149 | 2,38 | 0,239 | 2,51 | variável |
| 1018-00 / Stella | sim | 0,057 | 0,42 | 0,210 | 0,55 | variável |
| 1018-13 / ORB-SLAM3 | sim | 0,092 | 0,43 | 0,202 | 0,53 | variável |
| 1018-13 / Stella | sim | 0,154 | 1,96 | 1,580 | 2,34 | variável |
| rellis_example / ORB-SLAM3 | sim | 0,041 | 0,16 | 0,091 | 0,63 | variável |
| rellis_example / Stella | sim | 0,069 | 0,34 | 0,065 | 0,38 | variável |
| 00000 / ORB-SLAM3 | **não** (r3) | 0,548 | 4,87 | 25,29 | 8,59 | variável |
| 00000 / Stella | sim | 0,299 | 0,43 | 8,010 | 3,94 | variável |

- Componente A: em 7 combinações, `ok` e a segmentação foram idênticos nas três execuções. No 1018-13/ORB-SLAM3 as três
  execuções têm as mesmas 2 falhas e os mesmos 2 reinícios. No 00000/ORB-SLAM3, a execução 3 teve 1 falha e 1 reinício
  ausentes nas execuções 1 e 2, com 35 quadros de `ok` divergente (diferença de cobertura de 1,1 ponto percentual);
  as sobreposições foram comparadas separadamente (C com 2 sobreposições).
- B e C ficaram acima dos limiares (1 mm e 0,01°) em todos os pares, por várias ordens de grandeza. C mede a diferença
  acumulada entre execuções a partir de uma âncora comum; não é erro em relação ao GT.

**Decisão (seção 6):** as 8 combinações são variáveis. Pela regra, todas passam a dez execuções (r4–r10 em todas as
combinações, ~2 h 40 min em tempo real), e as métricas da fase 2 serão reportadas como distribuição sobre as dez.
**O escalonamento não foi iniciado:** aguarda revisão desta fase.

## Escalonamento para dez execuções (r4–r10) — 16/10/2026

Liberado após a revisão da fase 1. Execuções: `python -m ofd.run_vo_repeat --reps 4-10 --from-decisions
data/analysis/vo_repeat/phase1/decisions.json` (56 execuções, mesma ordem intercalada; registros com `repo_commit`
`a8bb1bd`, que difere de `084243d` só na documentação). Análise: `python -m ofd.vo_repeat --from-decisions
data/analysis/vo_repeat/phase1/decisions.json --out data/analysis/vo_repeat/phase1_escalated` (r1–r10, 45 pares por
combinação). Nenhuma métrica de erro (GT) foi calculada ou consultada.

**Execução.** 56/56 com código de saída 0, `status: finished`, tentativa 1; as 80 execuções (r1–r10) são válidas pela
seção 5.1. Razão relógio/sequência em r4–r10: 1,02 a 1,13. Carga média de 1 min no início: 2,8 a 8,3 (16 núcleos),
acima da faixa da fase 1 em algumas execuções (máximo em 00000/Stella r5, 1018-13/Stella r7, rellis_example/Stella r9
e 1018-13/ORB-SLAM3 r7, todas entre 7,3 e 8,3), sem outro experimento em paralelo.

**Hashes distintos entre as 10 execuções.** `poses_causal.tum` e `indicators.csv`: 10 em todas as combinações.
`state.csv`: 1 em seis combinações; 3 em 1018-13/ORB-SLAM3 e 6 em 00000/ORB-SLAM3.

**Componentes A, B e C** (máximo e mediana sobre os 45 pares; B e C no frame `cam_left`, sem GT):

| Combinação | A idêntico (pares) | B máx. t (m) | B máx. r (°) | C máx. t (m) | C máx. r (°) | C mediana t (m) | C mediana r (°) | Decisão |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1018-00 / ORB-SLAM3 | 45/45 | 0,207 | 3,49 | 0,540 | 6,03 | 0,219 | 2,60 | variável |
| 1018-00 / Stella | 45/45 | 0,072 | 0,49 | 0,309 | 0,74 | 0,184 | 0,50 | variável |
| 1018-13 / ORB-SLAM3 | **22/45** | 0,250 | 2,14 | 0,405 | 2,37 | 0,201 | 0,66 | variável |
| 1018-13 / Stella | 45/45 | 0,186 | 2,34 | 1,929 | 2,68 | 0,755 | 1,04 | variável |
| rellis_example / ORB-SLAM3 | 45/45 | 0,088 | 1,36 | 0,398 | 1,39 | 0,121 | 0,58 | variável |
| rellis_example / Stella | 45/45 | 0,199 | 0,35 | 0,256 | 0,54 | 0,065 | 0,23 | variável |
| 00000 / ORB-SLAM3 | **10/45** | 0,686 | 4,87 | 33,12 | 11,39 | 4,664 | 3,98 | variável |
| 00000 / Stella | 45/45 | 1,950 | 0,50 | 10,27 | 4,14 | 5,451 | 2,49 | variável |

- Componente A, só no ORB-SLAM3:
  - 1018-13: r1–r5, r8 e r9 têm 2 falhas e 2 reinícios (3 segmentos); r6, r7 e r10 têm 3 e 3 (4 segmentos).
    Diferença de cobertura até 2,0 pontos percentuais.
  - 00000: falhas/reinícios por execução — 0 (r1, r2, r6, r7, r10), 1 (r3, r4, r5, r9) e 3 (r8). Diferença de
    cobertura até 3,3 pontos percentuais; até 102 quadros de `ok` divergente (pares com r8).
  - Em todos os pares, B e C tiveram comparações definidas (B ≥ 1.500 e C ≥ 1.503 incrementos/poses no 1018-13;
    ≥ 2.926/2.931 no 00000), com até 3 e 5 sobreposições, respectivamente.
- B e C ficaram acima dos limiares (1 mm e 0,01°) em todos os 360 pares; o menor B máx. t foi 10,3 mm
  (rellis_example/Stella) e o menor C máx. t, 14,1 mm (idem).

**Decisão (seção 6):** as 8 combinações seguem variáveis com dez execuções. As métricas da fase 2 serão reportadas
como distribuição sobre r1–r10 (estatísticas da seção 7). **A fase 2 não foi iniciada:** exige liberação separada.

**Revisão — 19/10/2026.** Escalonamento aprovado. O revisor recalculou os 45 pares das oito combinações (máximos,
medianas, contagens de A e limites de B/C coincidem com esta seção), conferiu os 56 registros r4–r10 (carga inicial
2,82–8,27; razão relógio/sequência 1,017–1,134) e rodou os testes da implementação (70 aprovados). Carga da máquina:
r4–r10 não são invalidadas nem repetidas, porque o protocolo não fixou limiar, todas as execuções ficaram abaixo de 8,3
com 16 CPUs, sem outro experimento pesado, e parte da carga inicial é residual da execução anterior. A fase 2 não terá
limiar de carga, pois opera só sobre as saídas r1–r10 já produzidas; a reprodutibilidade é controlada por hashes das
entradas, commit, ambiente e testes, mantida a regra de não rodar outro experimento pesado em paralelo. Os três valores
extremos (B máx. t de 00000/Stella, C máx. t de 00000/ORB-SLAM3 e de 1018-13/Stella) ficam só como descrição.

**Liberação da fase 2, em duas etapas:** (1) implementar o orquestrador e o gerador de relatório da fase 2 — já existem
componentes reutilizáveis e testados (`ofd.evaluate`, `describe()`, `indicator_medians()`), mas a integração ponta a
ponta, a geração das tabelas da seção 7 e seus testes específicos precisam ser implementados e revisados antes da
execução; (2) rodar sobre r1–r10 nas 8 combinações, com a execução oficial reportada à parte (seção 8).

## Fase 2 — métricas como distribuição sobre r1–r10 — 19/10/2026

Liberada após a revisão da implementação (commit `eb90bfc`). Comando, executado a partir de `eb90bfc` com a árvore
limpa (1 min 34 s; não executa as VOs):

```
env -u PYTHONPATH .venv/bin/python -m ofd.vo_repeat_phase2 \
  --from-decisions data/analysis/vo_repeat/phase1/decisions.json --out data/analysis/vo_repeat/phase2
```

Saídas em `data/analysis/vo_repeat/phase2/`: `<seq>_<método>_runs.csv`, `summary.csv`, `success.csv` e
`official.csv`. Estatísticas da seção 7: média ± desvio-padrão amostral [mínimo–máximo]; contagens e trechos em
mediana [q1–q3]. O RPE rotacional é calculado em rad (unidade de `ofd.evaluate`) e aparece abaixo em graus.

**Execução e verificações.** 80/80 execuções válidas (taxa de sucesso 1,0 nas 8 combinações; todos os códigos de saída
0). Nenhuma métrica aplicável ficou indefinida: `n_defined` = 10 em todas as métricas de todas as combinações, e a
fração de indicadores ausentes nos quadros `ok = 1` é 0 em todas as execuções. Verificação cruzada da execução oficial
recalculada pela fase 2 (`official.csv`): nas quatro combinações do BotanicGarden, as dez métricas comuns coincidem
exatamente com `data/output/metrics.csv` do pipeline (diferença máxima 0). No RELLIS, coincidem exatamente as quatro
métricas aplicáveis — cobertura, falhas, reinícios e `longest_s`; `longest_m`, segmentos e elegíveis não são
reportados pela fase 2 (emenda da seção 7), e as métricas de erro são indefinidas nas duas fontes.

**BotanicGarden (com GT):**

| Combinação | ATE (m) | RPE 10 m t (m) | RPE 10 m r (°) | Cobertura (%) | Falhas | Reinícios | Segmentos | Elegíveis |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1018-00 / ORB-SLAM3 | 0,870 ± 0,008 [0,859–0,887] | 0,512 ± 0,003 [0,508–0,519] | 0,61 ± 0,06 [0,55–0,72] | 65,0 ± 0,0 [65,0–65,0] | 0 [0–0] | 0 [0–0] | 1 [1–1] | 1 [1–1] |
| 1018-00 / Stella | 1,157 ± 0,010 [1,139–1,172] | 0,636 ± 0,004 [0,629–0,642] | 0,61 ± 0,01 [0,58–0,62] | 65,0 ± 0,0 [65,0–65,0] | 0 [0–0] | 0 [0–0] | 1 [1–1] | 1 [1–1] |
| 1018-13 / ORB-SLAM3 | 1,169 ± 0,148 [0,887–1,249] | 0,469 ± 0,003 [0,467–0,475] | 0,65 ± 0,01 [0,63–0,68] | 74,3 ± 0,8 [73,2–74,8] | 2 [2–2,75] | 2 [2–2,75] | 3 [3–3,75] | 1 [1–1] |
| 1018-13 / Stella | 1,578 ± 0,038 [1,512–1,657] | 0,587 ± 0,007 [0,579–0,604] | 0,70 ± 0,06 [0,67–0,86] | 76,4 ± 0,0 [76,4–76,4] | 0 [0–0] | 0 [0–0] | 1 [1–1] | 1 [1–1] |

Maior trecho contínuo, mediana [q1–q3] (mínimo–máximo): 1018-00, 96,1 s e 114,0 m nos dois métodos, sem variação;
1018-13/Stella, 100,4 s e 122,7 m, sem variação; 1018-13/ORB-SLAM3, 96,9 s [96,9–96,9] (62,0–96,9) e 121,0 m
[121,0–121,0] (80,4–121,0).

**RELLIS-3D (sem GT, exploratório):**

| Combinação | Cobertura (%) | Falhas | Reinícios | Maior trecho contínuo (s) |
|---|---:|---:|---:|---:|
| rellis_example / ORB-SLAM3 | 83,6 ± 0,0 [83,6–83,6] | 0 [0–0] | 0 [0–0] | 1,7 [1,7–1,7] |
| rellis_example / Stella | 83,6 ± 0,0 [83,6–83,6] | 0 [0–0] | 0 [0–0] | 1,7 [1,7–1,7] |
| 00000 / ORB-SLAM3 | 84,5 ± 0,9 [82,3–85,1] | 0,5 [0–1] (0–3) | 0,5 [0–1] (0–3) | 3,5 [3,5–3,5] |
| 00000 / Stella | 85,1 ± 0,0 [85,1–85,1] | 0 [0–0] | 0 [0–0] | 3,5 [3,5–3,5] |

**Indicadores** (média ± desvio-padrão, entre execuções, das medianas por execução nos quadros `ok = 1`):

| Combinação | inliers | n_features | reproj_err (px) | tracked_ratio |
|---|---:|---:|---:|---:|
| 1018-00 / ORB-SLAM3 | 256,9 ± 3,5 | 1507 ± 0 | 1,497 ± 0,009 | 0,1966 ± 0,0023 |
| 1018-00 / Stella | 1069,0 ± 3,3 | 4255 ± 0 | 2,112 ± 0,009 | 0,2568 ± 0,0009 |
| 1018-13 / ORB-SLAM3 | 231,2 ± 1,1 | 1507 ± 0 | 1,484 ± 0,005 | 0,1831 ± 0,0013 |
| 1018-13 / Stella | 856,4 ± 4,1 | 4081 ± 0 | 2,105 ± 0,005 | 0,2187 ± 0,0010 |
| rellis_example / ORB-SLAM3 | 321,0 ± 3,3 | 1505 ± 0 | 1,404 ± 0,013 | 0,2626 ± 0,0043 |
| rellis_example / Stella | 224,0 ± 1,7 | 1510 ± 0 | 1,866 ± 0,002 | 0,1469 ± 0,0010 |
| 00000 / ORB-SLAM3 | 287,6 ± 1,7 | 1506 ± 0 | 1,424 ± 0,008 | 0,2391 ± 0,0014 |
| 00000 / Stella | 312,1 ± 2,4 | 1936 ± 0 | 2,074 ± 0,006 | 0,1561 ± 0,0007 |

**Execução oficial** (referência, fora das estatísticas; seção 8):

| Combinação | ATE (m) | RPE 10 m t (m) | RPE 10 m r (°) | Cobertura (%) | Falhas |
|---|---:|---:|---:|---:|---:|
| 1018-00 / ORB-SLAM3 | 0,877 | 0,510 | 0,58 | 65,0 | 0 |
| 1018-00 / Stella | 1,135 | 0,625 | 0,60 | 65,0 | 0 |
| 1018-13 / ORB-SLAM3 | 1,246 | 0,469 | 0,66 | 74,8 | 2 |
| 1018-13 / Stella | 1,601 | 0,586 | 0,68 | 76,4 | 0 |

No RELLIS, a execução oficial tem cobertura de 83,6 % (rellis_example) e 85,1 % (00000), sem falhas, nos dois
métodos.

**Observações descritivas** (sem reinterpretação; a seção 7 não prevê teste sobre elas):

- A cobertura, as falhas e os reinícios só variam onde o componente A já divergia (ORB-SLAM3 em 1018-13 e 00000); nas
  outras seis combinações são iguais nas dez execuções.
- 1018-13/ORB-SLAM3: o ATE tem dois grupos que acompanham a segmentação. r6 e r7 (3 falhas, 4 segmentos, 2 elegíveis,
  maior trecho de 62,0 s) têm ATE de 0,890 e 0,887 m; as outras oito, inclusive r10 (3 falhas, 4 segmentos, 1
  elegível), ficam entre 1,228 e 1,249 m. O desvio-padrão de 0,148 m reflete esses dois grupos. É a situação da
  ressalva da seção 7: o ATE de cada execução é calculado na própria segmentação, e as execuções não são pareadas. No
  RPE 10 m translacional a faixa é estreita (0,467–0,475 m), com r6 e r7 nos dois maiores valores (0,474 e 0,475 m).
- RELLIS: o maior trecho contínuo de 1,7 s e 3,5 s, igual nos dois métodos e nas dez execuções, decorre da grade do
  LiDAR (10 Hz) com câmera a 7,5 Hz (passos sem quadro novo ficam inválidos por desenho), já registrado em
  `docs/RESULTS_sequences.md`; não indica falha de rastreamento.
- `n_features` tem mediana constante por combinação (desvio 0).
