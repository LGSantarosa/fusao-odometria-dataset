# Resultados — modelo de fusão (protocolo `docs/protocol_fusion_model.md`)

## Fase 2 — teste confirmatório de 20/10/2026

**Situação: concluída. Resultado pela regra pré-registrada (seção 9): negativo para F1 e para F2.** Registro sem
reinterpretação; as observações descritivas abaixo não alteram a decisão.

**Execução.** Código `0ca8afc` (fase 1 revisada e fase 2 liberada em 20/10), árvore limpa e push feito antes da
execução. `python -m ofd.fusion_run phase2`, 13:49 → 13:53 (3 min 33 s), memória máxima 0,51 GB, código 0. Seleções
congeladas da fase 1 (`selected.json` de cada dobra); modelos finais com as sementes 0–4. Dobra A: treino 1018-00,
teste 1018-13 (1936 linhas com GT); dobra B: treino 1018-13, teste 1018-00 (1299 linhas). Nenhuma execução falhou.

**Regra de decisão** (F1 e F2 versus Bsel e B6; diferença > 2 desvios-padrão de sementes; positivo só se "sim" nas 4
linhas):

F1:

| Dobra | Métrica | Média | 2 dp | Bsel − média | B6 − média | Supera ambos? |
|---|---|---:|---:|---:|---:|---|
| A | rmse_v | 0,1564 | 0,0044 | +0,0322 | -0,0002 | não |
| A | rmse_w | 0,0291 | 0,0005 | +0,0330 | +0,0084 | sim |
| B | rmse_v | 0,1388 | 0,0008 | +0,0091 | -0,0127 | não |
| B | rmse_w | 0,0216 | 0,0011 | +0,0285 | +0,0018 | sim |

F2 (comparação):

| Dobra | Métrica | Média | 2 dp | Bsel − média | B6 − média | Supera ambos? |
|---|---|---:|---:|---:|---:|---|
| A | rmse_v | 0,1894 | 0,0194 | -0,0007 | -0,0331 | não |
| A | rmse_w | 0,0660 | 0,0014 | -0,0039 | -0,0285 | não |
| B | rmse_v | 0,1279 | 0,0013 | +0,0200 | -0,0019 | não |
| B | rmse_w | 0,0245 | 0,0005 | +0,0256 | -0,0011 | não |

`decision.json`: F1 `passed = false` (falha em `rmse_v` nas duas dobras; passa em `rmse_w` nas duas); F2
`passed = false` (falha nas quatro linhas).

**Métricas no teste** (primárias em m/s e rad/s; média ± desvio-padrão amostral sobre 5 sementes para F1 e F2;
secundárias são médias):

| Dobra | Modelo | RMSE v | RMSE ω | RPE t 10 m | RPE r 10 m (rad) | ATE (m) |
|---|---|---:|---:|---:|---:|---:|
| A | B1 | 0,2007 | 0,0626 | 0,635 | 0,0215 | 1,858 |
| A | B2 | 0,1887 | 0,0622 | 0,588 | 0,0165 | 2,144 |
| A | B3 | 0,1546 | 0,0654 | 0,100 | 0,0140 | 0,083 |
| A | B4 | 0,3294 | 0,0563 | 0,250 | 0,0534 | 1,826 |
| A | B5 | 0,1549 | 0,0372 | 0,245 | 0,0156 | 0,810 |
| A | Bsel | 0,1887 | 0,0622 | 0,588 | 0,0165 | 2,144 |
| A | B6 | 0,1563 | 0,0375 | 0,387 | 0,0520 | 2,901 |
| A | F1 | 0,1564 ± 0,0022 | 0,0291 ± 0,0003 | 0,276 | 0,0240 | 0,945 |
| A | F2 | 0,1894 ± 0,0097 | 0,0660 ± 0,0007 | 1,991 | 0,3270 | 17,264 |
| B | B1 | 0,1639 | 0,0435 | 0,514 | 0,0166 | 0,825 |
| B | B2 | 0,1673 | 0,0426 | 0,628 | 0,0152 | 1,029 |
| B | B3 | 0,1479 | 0,0501 | 0,087 | 0,0100 | 0,164 |
| B | B4 | 0,2423 | 0,0380 | 0,195 | 0,0301 | 0,132 |
| B | B5 | 0,1312 | 0,0242 | 0,273 | 0,0107 | 0,435 |
| B | Bsel | 0,1479 | 0,0501 | 0,087 | 0,0100 | 0,164 |
| B | B6 | 0,1261 | 0,0234 | 0,149 | 0,0292 | 0,307 |
| B | F1 | 0,1388 ± 0,0004 | 0,0216 ± 0,0006 | 0,333 | 0,0096 | 0,559 |
| B | F2 | 0,1279 ± 0,0007 | 0,0245 ± 0,0002 | 0,252 | 0,0383 | 1,458 |

B1–B4 = ORB-SLAM3, Stella, FAST-LIO, KISS-ICP com retenção causal; B5 = média das válidas; Bsel = melhor isolada
escolhida no treino (A: Stella; B: FAST-LIO); B6 = ridge.

**Observações descritivas (não decidem).**
- F1 tem o menor RMSE ω entre todos os modelos nas duas dobras (A: 0,0291 contra 0,0372 de B5, o melhor baseline;
  B: 0,0216 contra 0,0234 de B6). No RMSE v, F1 empata com B6 na dobra A (0,1564 contra 0,1563) e perde para B6, B5
  e F2 na dobra B.
- A média simples B5 supera Bsel nas duas primárias e nas duas dobras.
- F2 tem ATE de 17,3 m na dobra A (deriva na integração), contra 0,08 m de FAST-LIO isolado (B3).
- Pesos médios de F1 (`weights_f1.csv`): com 1 fonte válida, 100% KISS-ICP (único válido); com 2, predominância do
  FAST-LIO (A: 0,92; B: 0,77); com 4, pesos próximos do uniforme (0,17–0,30). Estrato de 3 fontes: n = 34 (A) e n = 0 (B,
  indefinido).
- RELLIS (exploratório, sem métricas de erro): predições gravadas em `phase2/rellis/predictions/` (40 arquivos);
  `agreement.csv` dá a diferença RMS entre os modelos das duas dobras.

### Tabelas complementares obrigatórias (seção 9 e 10 do protocolo)

**Estatísticas sobre as 5 sementes (F1 e F2).**

| Dobra | Modelo | Métrica | Média | dp | Mín. | Máx. |
|---|---|---:|---:|---:|---:|---:|
| A | F1 | RMSE v (m/s) | 0,1564 | 0,0022 | 0,1537 | 0,1592 |
| A | F1 | RMSE ω (rad/s) | 0,0291 | 0,0003 | 0,0288 | 0,0295 |
| A | F1 | RMSE ω (°/s) | 1,6681 | 0,0148 | 1,6496 | 1,6887 |
| A | F2 | RMSE v (m/s) | 0,1894 | 0,0097 | 0,1769 | 0,2000 |
| A | F2 | RMSE ω (rad/s) | 0,0660 | 0,0007 | 0,0649 | 0,0667 |
| A | F2 | RMSE ω (°/s) | 3,7828 | 0,0409 | 3,7158 | 3,8196 |
| B | F1 | RMSE v (m/s) | 0,1388 | 0,0004 | 0,1384 | 0,1395 |
| B | F1 | RMSE ω (rad/s) | 0,0216 | 0,0006 | 0,0208 | 0,0224 |
| B | F1 | RMSE ω (°/s) | 1,2353 | 0,0328 | 1,1909 | 1,2809 |
| B | F2 | RMSE v (m/s) | 0,1279 | 0,0007 | 0,1273 | 0,1287 |
| B | F2 | RMSE ω (rad/s) | 0,0245 | 0,0002 | 0,0242 | 0,0248 |
| B | F2 | RMSE ω (°/s) | 1,4024 | 0,0143 | 1,3869 | 1,4196 |

**RMSE ω dos baselines em °/s** (determinísticos).

| Dobra | Modelo | RMSE ω (°/s) |
|---|---|---:|
| A | B1 | 3,585 |
| A | B2 | 3,561 |
| A | B3 | 3,745 |
| A | B4 | 3,228 |
| A | B5 | 2,132 |
| A | Bsel | 3,561 |
| A | B6 | 2,150 |
| B | B1 | 2,492 |
| B | B2 | 2,442 |
| B | B3 | 2,868 |
| B | B4 | 2,176 |
| B | B5 | 1,389 |
| B | Bsel | 2,868 |
| B | B6 | 1,339 |

**Tabela por semente.**

| Dobra | Modelo | Semente | RMSE v | RMSE ω (rad/s) | RMSE ω (°/s) | RPE t 10 m | RPE r 10 m (rad) | ATE (m) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| A | F1 | 0 | 0,1575 | 0,0293 | 1,676 | 0,272 | 0,0235 | 0,716 |
| A | F1 | 1 | 0,1570 | 0,0290 | 1,663 | 0,262 | 0,0234 | 0,638 |
| A | F1 | 2 | 0,1549 | 0,0288 | 1,650 | 0,290 | 0,0242 | 1,165 |
| A | F1 | 3 | 0,1592 | 0,0295 | 1,689 | 0,273 | 0,0216 | 0,926 |
| A | F1 | 4 | 0,1537 | 0,0290 | 1,663 | 0,283 | 0,0274 | 1,281 |
| A | F2 | 0 | 0,1972 | 0,0649 | 3,716 | 1,998 | 0,3194 | 17,105 |
| A | F2 | 1 | 0,2000 | 0,0667 | 3,820 | 2,101 | 0,3287 | 15,242 |
| A | F2 | 2 | 0,1769 | 0,0661 | 3,788 | 1,907 | 0,3309 | 18,934 |
| A | F2 | 3 | 0,1825 | 0,0665 | 3,811 | 2,000 | 0,3340 | 18,020 |
| A | F2 | 4 | 0,1904 | 0,0660 | 3,779 | 1,951 | 0,3222 | 17,017 |
| B | F1 | 0 | 0,1387 | 0,0214 | 1,224 | 0,328 | 0,0095 | 0,602 |
| B | F1 | 1 | 0,1384 | 0,0224 | 1,281 | 0,348 | 0,0092 | 0,537 |
| B | F1 | 2 | 0,1388 | 0,0218 | 1,246 | 0,334 | 0,0104 | 0,525 |
| B | F1 | 3 | 0,1395 | 0,0215 | 1,234 | 0,329 | 0,0088 | 0,595 |
| B | F1 | 4 | 0,1385 | 0,0208 | 1,191 | 0,326 | 0,0102 | 0,535 |
| B | F2 | 0 | 0,1273 | 0,0244 | 1,399 | 0,271 | 0,0451 | 2,034 |
| B | F2 | 1 | 0,1277 | 0,0243 | 1,392 | 0,209 | 0,0286 | 0,663 |
| B | F2 | 2 | 0,1287 | 0,0242 | 1,387 | 0,195 | 0,0243 | 0,510 |
| B | F2 | 3 | 0,1285 | 0,0248 | 1,420 | 0,290 | 0,0438 | 1,529 |
| B | F2 | 4 | 0,1273 | 0,0247 | 1,415 | 0,293 | 0,0494 | 2,553 |

**RMSE por componente** (m/s e rad/s; média sobre sementes em F1 e F2).

| Dobra | Modelo | vx | vy | vz | ωx | ωy | ωz |
|---|---|---:|---:|---:|---:|---:|---:|
| A | B1 | 0,1435 | 0,0784 | 0,1164 | 0,0255 | 0,0497 | 0,0281 |
| A | B2 | 0,1223 | 0,0773 | 0,1211 | 0,0250 | 0,0499 | 0,0274 |
| A | B3 | 0,0920 | 0,0775 | 0,0971 | 0,0326 | 0,0424 | 0,0376 |
| A | B4 | 0,2002 | 0,1909 | 0,1789 | 0,0330 | 0,0434 | 0,0142 |
| A | B5 | 0,0867 | 0,0692 | 0,1082 | 0,0164 | 0,0285 | 0,0174 |
| A | Bsel | 0,1223 | 0,0773 | 0,1211 | 0,0250 | 0,0499 | 0,0274 |
| A | B6 | 0,1044 | 0,0632 | 0,0976 | 0,0162 | 0,0282 | 0,0187 |
| A | F1 | 0,0926 | 0,0736 | 0,1023 | 0,0152 | 0,0181 | 0,0170 |
| A | F2 | 0,1463 | 0,0662 | 0,1002 | 0,0153 | 0,0285 | 0,0575 |
| B | B1 | 0,1115 | 0,0899 | 0,0797 | 0,0220 | 0,0260 | 0,0270 |
| B | B2 | 0,1228 | 0,0805 | 0,0802 | 0,0206 | 0,0252 | 0,0275 |
| B | B3 | 0,0949 | 0,0883 | 0,0712 | 0,0234 | 0,0301 | 0,0325 |
| B | B4 | 0,1542 | 0,1473 | 0,1151 | 0,0222 | 0,0296 | 0,0085 |
| B | B5 | 0,0885 | 0,0650 | 0,0718 | 0,0129 | 0,0145 | 0,0145 |
| B | Bsel | 0,0949 | 0,0883 | 0,0712 | 0,0234 | 0,0301 | 0,0325 |
| B | B6 | 0,0805 | 0,0633 | 0,0735 | 0,0126 | 0,0173 | 0,0094 |
| B | F1 | 0,0938 | 0,0714 | 0,0732 | 0,0104 | 0,0119 | 0,0146 |
| B | F2 | 0,0838 | 0,0653 | 0,0713 | 0,0110 | 0,0134 | 0,0173 |

**Métricas secundárias definidas** (execuções com valor finito / execuções).

| Dobra | Modelo | RPE t 10 m | RPE r 10 m | ATE |
|---|---|---:|---:|---:|
| A | B1 | 1/1 | 1/1 | 1/1 |
| A | B2 | 1/1 | 1/1 | 1/1 |
| A | B3 | 1/1 | 1/1 | 1/1 |
| A | B4 | 1/1 | 1/1 | 1/1 |
| A | B5 | 1/1 | 1/1 | 1/1 |
| A | Bsel | 1/1 | 1/1 | 1/1 |
| A | B6 | 1/1 | 1/1 | 1/1 |
| A | F1 | 5/5 | 5/5 | 5/5 |
| A | F2 | 5/5 | 5/5 | 5/5 |
| B | B1 | 1/1 | 1/1 | 1/1 |
| B | B2 | 1/1 | 1/1 | 1/1 |
| B | B3 | 1/1 | 1/1 | 1/1 |
| B | B4 | 1/1 | 1/1 | 1/1 |
| B | B5 | 1/1 | 1/1 | 1/1 |
| B | Bsel | 1/1 | 1/1 | 1/1 |
| B | B6 | 1/1 | 1/1 | 1/1 |
| B | F1 | 5/5 | 5/5 | 5/5 |
| B | F2 | 5/5 | 5/5 | 5/5 |

**Primárias por estrato de fontes válidas** (RMSE v / RMSE ω; média sobre sementes em F1 e F2; descritivo).

| Dobra | Fontes | n | B1 | B2 | B3 | B4 | B5 | Bsel | B6 | F1 | F2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 1 | 121 | 0,045 / 0,007 | 0,041 / 0,003 | 0,055 / 0,008 | 0,122 / 0,005 | 0,122 / 0,005 | 0,041 / 0,003 | 0,117 / 0,006 | 0,122 / 0,005 | 0,052 / 0,004 |
| A | 2 | 232 | 0,047 / 0,023 | 0,049 / 0,022 | 0,055 / 0,009 | 0,105 / 0,005 | 0,065 / 0,006 | 0,049 / 0,022 | 0,065 / 0,009 | 0,055 / 0,008 | 0,068 / 0,010 |
| A | 3 | 34 | 0,730 / 0,056 | 0,101 / 0,027 | 0,124 / 0,065 | 0,172 / 0,039 | 0,094 / 0,027 | 0,101 / 0,027 | 0,153 / 0,029 | 0,087 / 0,028 | 0,178 / 0,034 |
| A | 4 | 1549 | 0,195 / 0,069 | 0,209 / 0,069 | 0,170 / 0,072 | 0,364 / 0,063 | 0,167 / 0,041 | 0,209 / 0,069 | 0,168 / 0,042 | 0,170 / 0,032 | 0,208 / 0,074 |
| B | 1 | 198 | 0,041 / 0,004 | 0,040 / 0,003 | 0,056 / 0,005 | 0,123 / 0,006 | 0,123 / 0,006 | 0,056 / 0,005 | 0,082 / 0,021 | 0,123 / 0,006 | 0,055 / 0,005 |
| B | 2 | 148 | 0,038 / 0,004 | 0,037 / 0,003 | 0,054 / 0,008 | 0,124 / 0,007 | 0,074 / 0,006 | 0,054 / 0,008 | 0,047 / 0,006 | 0,057 / 0,006 | 0,051 / 0,004 |
| B | 3 | 0 | indef. | indef. | indef. | indef. | indef. | indef. | indef. | indef. | indef. |
| B | 4 | 953 | 0,190 / 0,051 | 0,194 / 0,050 | 0,169 / 0,058 | 0,273 / 0,044 | 0,139 / 0,028 | 0,169 / 0,058 | 0,141 / 0,025 | 0,150 / 0,025 | 0,146 / 0,028 |

**Pesos médios de F1** (média sobre sementes; global e por estrato).

| Dobra | Estrato | n | ORB-SLAM3 | Stella | FAST-LIO | KISS-ICP |
|---|---|---:|---:|---:|---:|---:|
| A | 1 | 121 | 0,000 | 0,000 | 0,000 | 1,000 |
| A | 2 | 232 | 0,000 | 0,000 | 0,919 | 0,081 |
| A | 3 | 34 | 0,000 | 0,529 | 0,317 | 0,155 |
| A | 4 | 1549 | 0,234 | 0,258 | 0,284 | 0,223 |
| A | global | 1936 | 0,187 | 0,216 | 0,343 | 0,254 |
| B | 1 | 198 | 0,000 | 0,000 | 0,000 | 1,000 |
| B | 2 | 148 | 0,000 | 0,000 | 0,768 | 0,232 |
| B | 3 | 0 | indef. | indef. | indef. | indef. |
| B | 4 | 953 | 0,280 | 0,297 | 0,253 | 0,169 |
| B | global | 1299 | 0,206 | 0,218 | 0,273 | 0,303 |

**RELLIS-3D (exploratório; só descrições, seção 10)** — média sobre as 5 sementes: rapidez prevista (m/s), seu dp ao longo da sequência, taxa média de guinada (°/s) e pesos médios de F1.

| Sequência | Dobra | Modelo | Falhas | Rapidez média | dp | Guinada (°/s) | w ORB | w Stella | w FAST-LIO | w KISS |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 00000 | A | F1 | 0 | 1,169 | 0,587 | -0,233 | 0,149 | 0,195 | 0,141 | 0,514 |
| 00000 | A | F2 | 0 | 0,179 | 0,081 | 3,908 | — | — | — | — |
| 00000 | B | F1 | 0 | 1,155 | 0,580 | -0,246 | 0,227 | 0,397 | 0,291 | 0,085 |
| 00000 | B | F2 | 0 | 0,379 | 0,174 | 0,155 | — | — | — | — |
| rellis_example | A | F1 | 0 | 0,924 | 0,493 | 0,312 | 0,203 | 0,252 | 0,156 | 0,387 |
| rellis_example | A | F2 | 0 | 0,158 | 0,073 | 3,555 | — | — | — | — |
| rellis_example | B | F1 | 0 | 0,912 | 0,482 | 0,326 | 0,241 | 0,394 | 0,246 | 0,118 |
| rellis_example | B | F2 | 0 | 0,282 | 0,150 | 0,379 | — | — | — | — |

**Concordância entre as dobras no RELLIS** (diferença RMS entre as predições dos modelos A e B da mesma semente; média, mín.–máx. sobre sementes).

| Sequência | Modelo | Δv RMS (m/s) | Δω RMS (°/s) |
|---|---|---:|---:|
| 00000 | F1 | 0,183 (0,103–0,269) | 1,211 |
| 00000 | F2 | 0,430 (0,385–0,496) | 5,262 |
| rellis_example | F1 | 0,136 (0,053–0,242) | 0,701 |
| rellis_example | F2 | 0,342 (0,318–0,385) | 4,353 |

Artefatos (fora do git):

| Arquivo | SHA-256 |
|---|---|
| `data/analysis/fusion/phase2/test_metrics.csv` | `768ae07de1b83fb6a77b55e9b6cca52cb7c11cb8aab5c114e7f5467072c156b4` |
| `data/analysis/fusion/phase2/stratified.csv` | `97c7b47c0f093b10de91247926a2b016b64c3a743934ad0593ad0856f0b7bf97` |
| `data/analysis/fusion/phase2/weights_f1.csv` | `6164b3b8a8cac906eca30e5c117cd3ea7ce985f663097e995914657075499827` |
| `data/analysis/fusion/phase2/decision.json` | `c840ab7fc9e64f366b50ec3d147eac62683f48f3729e55f162482cd3fbacfd30` |
| `data/analysis/fusion/logs/phase2.log` | `7a001391e3ca8d47d0fdc7d8daaca76a90cd1520b97d46f5208c3ea8f226fe8b` |

---

## Fase 1 — execução de 20/10/2026 (válida; revisada)

**Situação: concluída e revisada; fase 2 liberada em 20/10/2026.** Substitui a execução invalidada de 19/10 (abaixo).
Código `77d70ba` (correção `eaf4983` + emenda do clipe em ±10, seção 5), árvore limpa, push feito antes da execução,
dobras em série, nada mais em paralelo. Só a sequência de treino de cada dobra foi lida; nenhuma métrica na sequência
de teste.

| Dobra | Treino | Comando | Início → fim | Duração | Memória máx. | Saída |
|---|---|---|---|---:|---:|---|
| A | 1018-00 (1299 linhas com GT) | `python -m ofd.fusion_run phase1 --fold A` | 10:09 → 11:23 | 1 h 14 min | 0,46 GB | código 0 |
| B | 1018-13 (1936 linhas com GT) | `python -m ofd.fusion_run phase1 --fold B` | 11:23 → 13:35 | 2 h 12 min | 0,48 GB | código 0 |

Integridade estrutural (as duas dobras): 595 registros em `cv.csv` (B1–B4: 5 cada; B6: 35; F1 e F2: 270 cada),
subdobras 0–4, sementes 0–2, nenhuma execução falha, nenhuma perda não finita; `selected.json` com a dobra e a
sequência de treino corretas.

**Seleções (perda L média de validação interna; empate L ≤ 1,01 L_min resolvido pela mais simples, seção 7).**

| Dobra | Família | Escolha | L | L_min da família | Perda por subdobra (0 / 1 / 2 / 3 / 4) |
|---|---|---|---:|---:|---|
| A | Bsel | Stella | 0,566 | — | 0,727 / 0,621 / 0,922 / 0,549 / 0,011 |
| A | B6 | α = 100 (empata com α = 10) | 0,293 | 0,293 | 0,390 / 0,338 / 0,336 / 0,235 / 0,167 |
| A | F1 | 64 × 2, decaimento 1e-3, 43 épocas | 0,287 | 0,287 | 0,344 / 0,350 / 0,375 / 0,241 / 0,126 |
| A | F2 | 64 × 1, decaimento 1e-2, 278 épocas | 0,248 | 0,248 | 0,337 / 0,315 / 0,348 / 0,219 / 0,018 |
| B | Bsel | FAST-LIO | 0,618 | — | 0,402 / 1,570 / 0,681 / 0,346 / 0,090 |
| B | B6 | α = 1 (empata com α = 0,1 e 0,01) | 0,372 | 0,372 | 0,216 / 0,894 / 0,512 / 0,163 / 0,073 |
| B | F1 | 32 × 1, decaimento 1e-3, 88 épocas (5 empatadas; L_min em 64 × 2) | 0,375 | 0,373 | 0,200 / 0,885 / 0,557 / 0,149 / 0,084 |
| B | F2 | 64 × 1, decaimento 1e-2, 475 épocas | 0,357 | 0,357 | 0,178 / 0,852 / 0,558 / 0,143 / 0,055 |

A explosão da subdobra 4 da execução invalidada não se repete: em todas as famílias a subdobra 4 tem a menor perda
(o bloco final é quase parado: velocidade média do GT 0,04 m/s no 1018-00 e 0,38 m/s no 1018-13, contra 0,76–1,38 m/s
nos demais; as odometrias isoladas também ficam em 0,01–0,09 ali). Desvio entre
sementes por subdobra da configuração escolhida: ≤ 0,013 (F1) e ≤ 0,011 (F2). Estas perdas são de validação interna e
servem só à seleção; a comparação da regra de decisão (seção 9) é feita apenas na fase 2.

Artefatos (fora do git):

| Arquivo | SHA-256 |
|---|---|
| `data/analysis/fusion/phase1/A/cv.csv` | `326cab1eea80c9f48c7032e5c0660272868a3556b0ef2aa17e757dccfa0d8565` |
| `data/analysis/fusion/phase1/A/selected.json` | `40d271933587c75d5f12de57f954525df125afcf8028063ef3aa4de2dc7ec8f0` |
| `data/analysis/fusion/phase1/B/cv.csv` | `b3b5080c0a958357eb00f20224ca1562660b7ea77a158465a89510e8b5c88ee5` |
| `data/analysis/fusion/phase1/B/selected.json` | `b45b3492e687d8180eafb2d5b451d0e9cd7111a444b6719bf29b0227bb25270b` |
| `data/analysis/fusion/logs/phase1_A.log` | `b02da1c51ca04f5d86dcdb59fca47de7730e35b760f67ca1454b1376dc9b0e3f` |
| `data/analysis/fusion/logs/phase1_B.log` | `28303f4942d7cfd5719121cae2110b8eecc7ed8f7d441ea242cbf52e2370005d` |


## Fase 1 — execução de 19/10/2026 invalidada por defeito de implementação

**Situação: inválida.** As duas dobras rodaram até o fim sem falha, mas a padronização violou a seção 5 do protocolo
(linhas com o método inválido não recebiam 0 em todas as entradas desse método). As seleções desta execução **não
podem ser usadas** na fase 2. O defeito foi corrigido com teste (abaixo); a fase 1 precisa ser repetida após a revisão
da correção e de uma lacuna do protocolo. Nenhuma métrica foi calculada na sequência de teste de nenhuma dobra.

**Execução.** Código `3c34457` (fase 0 aprovada), árvore limpa, uma dobra por vez, nada mais em paralelo.

| Dobra | Treino | Comando | Início → fim | Duração | Memória máx. | Saída |
|---|---|---|---|---:|---:|---|
| A | 1018-00 (1299 linhas com GT) | `python -m ofd.fusion_run phase1 --fold A` | 13:10 → 14:34 | 1 h 24 min | 0,52 GB | código 0 |
| B | 1018-13 (1936 linhas com GT) | `python -m ofd.fusion_run phase1 --fold B` | 14:35 → 16:39 | 2 h 05 min | 0,54 GB | código 0 |

Integridade estrutural (as duas dobras): 595 registros em `cv.csv` (B1–B4: 5 cada; B6: 35; F1 e F2: 270 cada),
subdobras 0–4, sementes 0–2, nenhuma execução falha, nenhuma perda não finita; `selected.json` com a dobra e a
sequência de treino corretas.

Artefatos preservados para auditoria, renomeados para não serem usados por engano (fora do git):

| Arquivo | SHA-256 |
|---|---|
| `data/analysis/fusion/phase1_invalid_3c34457/A/cv.csv` | `bc48ecac8acdb8c91ec27d078d936c6af0c9aa94c32267743407a3c31f3b7bda` |
| `data/analysis/fusion/phase1_invalid_3c34457/A/selected.json` | `039dc5ecebaeda2c647c096f7375ebf19909b94fc6cf9e3951f9ff5ee7fef510` |
| `data/analysis/fusion/phase1_invalid_3c34457/B/cv.csv` | `37be3bfc85811501ba987628df87c9b0c6ac4412b37467a467b2eec52b1789e3` |
| `data/analysis/fusion/phase1_invalid_3c34457/B/selected.json` | `3bae353b488cfd5915ffb54c157d7ff9e0b180f996584558b37be08f7285cba6` |
| `data/analysis/fusion/phase1_invalid_3c34457/logs/phase1_A.log` | `4c721cdd179383df30ec2d86e4c5882f568861f8e4590e57937b5c4afe64b96e` |
| `data/analysis/fusion/phase1_invalid_3c34457/logs/phase1_B.log` | `9e0308d2468c92b824fc78676a92cc4a01a2f562a852466e58791bd40beb73ed` |

**Sintoma.** A perda de validação da configuração escolhida de B6 e F2 ficou na casa dos milhares (A: 2215 e 7437;
B: 6659 e 4789), contra 0,3–1,9 nos baselines e em F1. A perda explode só na subdobra 4 (fim de cada sequência):

| Dobra | Família | Perda por subdobra (0 / 1 / 2 / 3 / 4) |
|---|---|---|
| A | B6 | 0,535 / 0,441 / 0,470 / 0,387 / 11074,9 |
| A | F2 | 0,380 / 0,350 / 0,460 / 0,255 / 37182,7 |
| B | B6 | 0,290 / 0,883 / 0,546 / 0,158 / 33294,8 |
| B | F2 | 0,271 / 0,936 / 0,636 / 0,173 / 23941,2 |

**Causa (defeito de implementação).** No dataset, linhas com o método inválido ainda trazem `dt_ms`, `age_ms` e a
variância móvel com valores antigos (ex.: a idade de uma pose do FAST-LIO depois que ele deixa de estimar). O
`Standardizer` só imputava valores ausentes (NaN), e esses valores entravam padronizados: `fastlio_dt_ms` chegou a 56
857σ (A) e 64 502σ (B) nas linhas inválidas do bloco final; `fastlio_age_ms`, a 19 970σ e 12 002σ. Colunas afetadas
(linhas com GT em que o método é inválido mas a coluna tem valor, 1018-00 / 1018-13): `orbslam3_dt_ms` 321/297,
`orbslam3_age_ms` 322/298, `stella_dt_ms` 321/263, `stella_age_ms` 322/264, `fastlio_dt_ms` 198/119, `fastlio_age_ms`
198/120 e as variâncias móveis dos três métodos (8–10). Os dados sintéticos da fase 0 tinham NaN nessas posições, por
isso os testes não detectaram o problema. Como as entradas de todas as famílias aprendidas passam pela padronização, a
execução inteira fica inválida, não só B6 e F2.

**Correção (com teste).** `Standardizer.transform` passa a atribuir 0 a todas as entradas de um método nas linhas em
que ele é inválido (exceto `valid`), como diz a seção 5. Teste novo:
`tests/test_fusion_data.py::test_invalid_method_rows_are_imputed_even_when_raw_values_exist` (falhou antes da
correção com valores de até 3,7 × 10²⁰). Suíte: 282 testes.

**Lacuna do protocolo (decidida em 20/10/2026: clipe em ±10, emenda na seção 5 e no §14 do protocolo).** Depois da correção, medindo só nos dados de
treino de cada dobra, os maiores valores padronizados nos blocos de validação ficam entre 4σ e 62σ, exceto
`kissicp_dt_ms` na subdobra 4 do 1018-13: 1636σ numa linha válida. A coluna é quase constante no treino (100,9 ms,
σ ≈ 0,0016) e o protocolo só trata desvio exatamente zero. No treino completo, colunas com escala menor que 0,01:
1018-00 — `fastlio_dt_ms` 0,0018, `kissicp_dt_ms` 0,0018, `kissicp_wx` 0,0092 e as variâncias móveis do FAST-LIO
e do KISS-ICP (0,0010 e 0,0006); 1018-13 — as variâncias móveis do FAST-LIO e do KISS-ICP (0,0013 e 0,0007). Sem
uma regra pré-registrada, modelos lineares (B6) e F2 podem extrapolar nessas colunas. Possíveis emendas, a decidir
antes da nova execução: limitar os valores padronizados a ±k; impor uma escala mínima por coluna; ou manter o texto
atual e registrar a limitação.

**Seleções desta execução (inválidas; só para auditoria).** A: Bsel Stella, B6 α = 1000, F1 64 × 2 com decaimento
1e-3 (14 épocas), F2 16 × 2 com 1e-2 (388 épocas). B: Bsel FAST-LIO, B6 α = 100, F1 32 × 1 com 1e-4 (44 épocas),
F2 16 × 2 com 1e-2 (484 épocas).

**Próximo passo:** correção revisada e lacuna resolvida pela emenda de 20/10/2026; fase 1 repetida em 20/10/2026
(seção acima). A fase 2 continua bloqueada.
