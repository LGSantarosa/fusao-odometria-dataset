# Resultados — investigação do KISS-ICP (protocolo `docs/protocol_kissicp.md`)

## Fase 1 — repetibilidade (H4), decidida antes de abrir métricas de erro — 15/10/2026

Código: `14e9830`. Execuções: 3 repetições por condição e sequência (54 + 6 de D4′), 3 em paralelo, em
`data/runs/<seq>/kissicp_<C>_r<k>`; script `data/analysis/kissicp/logs/run_one.sh`, lista de tarefas em
`data/analysis/kissicp/logs/jobs*.txt`, saída da auditoria em `data/analysis/kissicp/h4_repeatability.txt`.
Nenhuma métrica de erro (ATE, RPE, erro por 100 m) foi calculada ou consultada nesta fase.

| Sequência | Condições | Hashes distintos entre as 3 repetições | máx. ΔSE(3) | Decisão |
|---|---|---|---|---|
| 1018-00 | D0, D1, D2, D3, D4, D4′ | 1 em cada condição | ≤ 7,4·10⁻¹⁵ m, 0° | determinístico |
| 1018-13 | D0, D1, D2, D3, D4, D4′ | 1 em cada condição | ≤ 8,2·10⁻¹⁵ m, 0° | determinístico |
| rellis_example | D0, D1, D2, D3 | 1 em cada condição | ≤ 7,3·10⁻¹⁵ m, 0° | determinístico |
| 00000 | D0, D1, D2, D3 | 1 em cada condição | ≤ 4,1·10⁻¹⁴ m, 0° | determinístico |

(ΔSE(3) não nulo com hashes idênticos é arredondamento do cálculo de inv(A)·A.)

**Decisão H4:** o KISS-ICP 1.3.0 é determinístico neste ambiente em todas as condições. Conforme a seção 5, usa-se a
repetição 1 de cada condição, sem intervalos artificiais e sem escalonar para dez execuções. H4 é rejeitada como
explicação do erro.

**Verificações de implementação (sem métricas de erro).**
- As condições produzem trajetórias distintas entre si (hashes diferentes em todas as sequências).
- D0 reproduz bit a bit a saída oficial `data/runs/<seq>/kissicp` nas quatro sequências.

**Diagnóstico t × t_geo (D3, sentido horário) e regra de D4′.**

| Sequência | correlação mediana | \|Δ\| mediano (ms) | scans |
|---|---:|---:|---:|
| 1018-00 | 0,950 | 0,42 | 1466 |
| 1018-13 | 0,950 | 0,43 | 2071 |
| rellis_example | 0,943 | 0,68 | 599 |
| 00000 | 0,960 | 0,64 | 2849 |

A correlação ficou abaixo de 0,99 em todas as sequências, o que aciona a regra pré-registrada: D4′ foi executado no
1018-00 e no 1018-13 (3 repetições, determinístico, trajetória distinta de D4). O |Δ| mediano ficou abaixo de 1 ms.

**Cobertura de D4/D4′:** scans compensados pelo GT / sem GT ao redor (não compensados, contados à parte):
1018-00 1299 / 167; 1018-13 1936 / 135.

## Fase 2 — métricas de erro, promoção e atribuição — 16/10/2026

Liberada pelo revisor em 15/10/2026 com seis regras: (1) só a repetição 1 (`kissicp_<C>_r1`); r2/r3 não são amostras
nem servem para selecionar; (2) métricas pareadas no suporte comum de GT; (3) critérios de promoção aplicados
literalmente, só a D1–D3; (4) D4/D4′ só para atribuição diagnóstica; (5) RELLIS exploratório, sem GT; (6) resultados
negativos e causas não identificadas registrados sem reinterpretar critérios. Métricas de erro calculadas só no
1018-00 e no 1018-13.

**Comandos (código `a91628c` + `tools/kissicp_phase2.py`).**

```bash
for s in 1018-00 1018-13; do
  env -u PYTHONPATH .venv/bin/python -m ofd.kissicp_analysis --seq-dir data/extracted/$s \
    $(for c in D0 D1 D2 D3 D4 D4prime; do echo --run $c=data/runs/$s/kissicp_${c}_r1; done) \
    --out data/analysis/kissicp/phase2/$s
done
env -u PYTHONPATH .venv/bin/python -m tools.kissicp_phase2 > data/analysis/kissicp/phase2/report.txt
```

**Correção operacional antes da análise de H3.** O runner da ablação grava `indicators.csv` só com `ts_ns`; os
indicadores uniformes (`fitness`, `inlier_rmse`, `unmatched_ratio`) são calculados por um passo separado
(`ofd.lidar_indicators`) que o `run_one.sh` da fase 1 não incluía. Esse passo foi executado sobre `kissicp_D0_r1` nas
quatro sequências (sem reexecutar o estimador; logs em `data/analysis/kissicp/logs/indicators_*_D0_r1.log`). O
resultado coincide com o do run oficial `kissicp` (diferença máxima 2·10⁻¹⁶), coerente com a identidade bit a bit de
D0_r1 já verificada na fase 1. As métricas de erro não dependem desses arquivos (resumo inalterado, |Δ| ≤ 4·10⁻¹⁶).

### Suporte comum e métricas

Suporte comum: 1.300 poses (1018-00) e 1.937 poses (1018-13), idêntico para as seis condições. Cobertura 100% e zero
falhas em todas as condições. D0 reproduz a evidência anterior (ATE 0,132 m no 1018-00 e 1,827 m no 1018-13).

| Seq. | Cond. | RPE 10 m t (m) | RPE 10 m r (°) | ATE (m) | RPE/quadro t (cm) | RPE/quadro r (°) | erro/100 m t (%) | erro/100 m r (°) | ATE 100 m iniciais (m) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1018-00 | D0 | 0,195 | 1,727 | 0,132 | 2,45 | 0,220 | 0,210 | 1,60 | 0,145 |
| 1018-00 | D1 | 0,215 | 1,775 | 0,132 | 4,09 | 0,302 | 0,143 | 1,65 | 0,154 |
| 1018-00 | D2 | 0,221 | 1,835 | 0,138 | 3,87 | 0,277 | 0,144 | 1,46 | 0,158 |
| 1018-00 | D3 | 0,213 | 1,748 | 0,130 | 4,06 | 0,314 | 0,141 | 1,38 | 0,149 |
| 1018-00 | D4 | 0,197 | 1,624 | 0,115 | 3,23 | 0,206 | 0,129 | 1,57 | 0,134 |
| 1018-00 | D4′ | 0,197 | 1,622 | 0,114 | 3,23 | 0,205 | 0,127 | 1,58 | 0,132 |
| 1018-13 | D0 | 0,250 | 3,061 | 1,827 | 3,32 | 0,326 | 2,503 | 11,40 | 0,579 |
| 1018-13 | D1 | 0,215 | 1,829 | 0,648 | 6,08 | 0,420 | 1,890 | 3,98 | 0,239 |
| 1018-13 | D2 | 0,317 | 3,156 | 1,709 | 5,72 | 0,446 | 3,026 | 11,51 | 0,623 |
| 1018-13 | D3 | 0,214 | 1,829 | 0,642 | 6,08 | 0,419 | 1,832 | 3,94 | 0,232 |
| 1018-13 | D4 | 0,185 | 1,686 | 0,608 | 4,09 | 0,290 | 1,576 | 3,43 | 0,216 |
| 1018-13 | D4′ | 0,173 | 1,669 | 0,588 | 4,02 | 0,291 | 1,584 | 3,47 | 0,225 |

Erro/100 m: RMSE sobre todas as subsequências de 100 m. Erro rotacional final após alinhamento (secundária): 1018-00
D0 1,05°, D1 0,28°, D2 0,31°, D3 0,28°, D4 0,19°, D4′ 0,19°; 1018-13 D0 1,77°, D1 7,11°, D2 1,58°, D3 7,11°,
D4 6,64°, D4′ 6,45°. Tabelas: `data/analysis/kissicp/phase2/summary_all.csv`, `relative_to_d0_pct.csv`.

### Promoção (seção 8, literal, só D1–D3)

| Cond. | Seq. | RPE 10 m t −5% | RPE 10 m r −5% | ATE ≤ +5% | cobertura | falhas | promove na seq. |
|---|---|---|---|---|---|---|---|
| D1 | 1018-00 | não (+10,0%) | não (+2,8%) | sim (+0,3%) | sim | sim | **não** |
| D1 | 1018-13 | sim (−14,0%) | sim (−40,2%) | sim (−64,5%) | sim | sim | sim |
| D2 | 1018-00 | não (+12,9%) | não (+6,3%) | sim (+4,6%) | sim | sim | **não** |
| D2 | 1018-13 | não (+26,5%) | não (+3,1%) | sim (−6,5%) | sim | sim | **não** |
| D3 | 1018-00 | não (+8,9%) | não (+1,2%) | sim (−1,9%) | sim | sim | **não** |
| D3 | 1018-13 | sim (−14,4%) | sim (−40,2%) | sim (−64,9%) | sim | sim | sim |

**Decisão: nenhuma candidata atende a todos os critérios nas duas sequências; D0 (`deskew = False`) é mantida.**
D1 e D3 atenderam a todos os itens no 1018-13 e falharam nos dois itens de RPE no 1018-00. O critério exige as duas
sequências separadamente, e não foi reinterpretado. Tabela: `data/analysis/kissicp/phase2/promotion.csv`.

### Q1 — onde está o erro do D0 no 1018-13

Normalizado pela distância, o 1018-13 é mais difícil, e não apenas mais longo: o erro por 100 m é 2,50% e 11,4°/100 m,
contra 0,21% e 1,6°/100 m no 1018-00; nos primeiros 100 m de cada sequência, o ATE é 0,579 m contra 0,145 m.

Localização (janelas de 10 m; descritivo, não causal; `phase2/1018-13/q1_localization.csv`): os 10% de janelas com
maior erro rotacional de D0 têm velocidade angular média por scan maior (mediana 1,19° contra 0,55° nas demais 90%)
e maior |Δω| máximo (0,57 contra 0,18 rad/s). Cada grupo de topo (rotacional, translacional) é comparado com o
próprio complemento; para o erro translacional, 1,17° contra 0,56° e 0,57 contra 0,19 rad/s. Correlação de Spearman com o erro rotacional: ωΔt 0,39; |Δω| 0,41;
vΔt −0,30. No 1018-00 essas correlações ficam entre −0,17 e 0,01, e a sequência não alcança regimes de rotação tão
altos (ωΔt máximo por scan 3,7° contra 6,3°).

### H3 — medidas de estrutura (seção 7, fallback PCA + indicadores)

No 1018-13, os 10% de janelas de maior erro rotacional comparados com as demais (medianas) mostram indicadores
mistos. Alguns não sugerem redução de estrutura: mais voxels ocupados (3.016 contra 2.726), menor linearidade (0,19
contra 0,30) e espalhamento ligeiramente maior (0,0384 contra 0,0377; Spearman com o erro rotacional 0,55). Outros vão
no sentido compatível com registro mais difícil: maior planaridade (0,770 contra 0,657; Spearman 0,40), *fitness*
menor (0,884 contra 0,910), `inlier_rmse` maior (0,176 contra 0,156) e `unmatched_ratio` maior (0,047 contra 0,032).
**H3 permanece inconclusiva e não atribuída: os proxies geométricos não mostram redução inequívoca de estrutura.**
Os indicadores de registro descrevem registro pior nesses trechos, mas não distinguem degenerescência de outras causas
(por exemplo, distorção sob rotação rápida). A forma da matriz de informação 6×6 não estava disponível pela API (fallback já
registrado na seção 10 do protocolo). No 1018-00 as medidas de estrutura não se associam ao erro (|ρ| ≤ 0,19).

### Atribuição de causa (seção 8), elemento por elemento

Estratificação pré-registrada: RPE por quadro por quartil de ωΔt, |Δω| e vΔt (`phase2/<seq>/frame_strata.csv`). A
mesma estratificação em janelas de 10 m **não** foi pré-registrada e está separada como post hoc
(`window_strata_posthoc.csv`).

RPE rotacional por quadro, variação em relação a D0 por quartil de ωΔt (Q0 baixo → Q3 alto):

| Seq. | Cond. | Q0 | Q1 | Q2 | Q3 |
|---|---|---:|---:|---:|---:|
| 1018-00 | D1 | −25,7% | +21,1% | +15,9% | +44,5% |
| 1018-00 | D3 | −22,0% | +24,7% | +17,2% | +51,2% |
| 1018-00 | D4 | −27,7% | +18,7% | −11,6% | −6,1% |
| 1018-13 | D1 | +59,4% | +40,7% | +29,6% | +27,4% |
| 1018-13 | D3 | +66,9% | +44,0% | +35,9% | +24,7% |
| 1018-13 | D4 | +20,9% | −5,0% | −19,5% | −8,9% |

RPE rotacional em janelas de 10 m por quartil de ωΔt médio da janela (**post hoc**):

| Seq. | Cond. | Q0 | Q1 | Q2 | Q3 |
|---|---|---:|---:|---:|---:|
| 1018-00 | D1 | −0,4% | +0,5% | +8,3% | +3,5% |
| 1018-00 | D4 | −6,5% | −6,5% | −4,5% | −6,1% |
| 1018-13 | D1 | +6,0% | −12,5% | −45,7% | −60,3% |
| 1018-13 | D4 | −9,9% | −23,4% | −45,1% | −62,0% |

- **H4 (não determinismo):** rejeitada na fase 1.
- **H2 (tempo por ponto incorreto):** previsão "D3 melhor que D1" não observada. D3 em relação a D1, RPE 10 m t/r e
  ATE: 1018-00 −1,0% / −1,5% / −2,1%; 1018-13 −0,4% / 0,0% / −1,1%. O protocolo não fixou limiar para atribuição; as
  diferenças são inferiores aos 5% usados na promoção. D2 é pior que D1 nas duas sequências (1018-13: +47% no RPE 10 m
  t, ATE 1,71 m contra 0,65 m), logo o sentido do campo não está invertido. **H2 não é sustentada.**
- **H1 (distorção não compensada):** D4 é melhor que D0 no 1018-13 em todas as métricas de 10 m e no ATE; no 1018-00
  só no RPE 10 m rotacional (−6,0%) e no ATE (−12,8%), não no translacional (+0,9%). Pela estratificação
  pré-registrada, a melhora rotacional de D4 **não** se concentra no quartil superior de ωΔt (1018-13: maior melhora
  em Q2; 1018-00: maior em Q0). **H1 não é atribuída pelo teste pré-registrado.** Na análise post hoc por janelas de
  10 m, o 1018-13 apresenta exatamente o padrão de H1 (melhora crescente com ωΔt, −62% em Q3); por não ter sido
  pré-registrada, essa observação fica como hipótese para trabalho futuro, não como atribuição.
- **H5 (modelo de movimento `last_delta`):** exige D4 melhor que D0 **e** D1 e D3 piores nos mesmos trechos de maior
  |Δω|. No 1018-00, o RPE rotacional por quadro de D1 e D3 piora monotonamente com |Δω| (D1 +4,7% → +45,5%; D3 +4,3%
  → +53,1%), enquanto D4 melhora (−24,9% → +1,0%); mas D4 não é melhor que D0 no RPE translacional (10 m +0,9%; por
  quadro +32,1%). No 1018-13, D1 e D3 melhoram D0 em 10 m, e o RPE por quadro piora em todos os quartis, sem
  concentração em |Δω| alto. **H5 não é atribuída**; o componente rotacional do 1018-00 é parcialmente compatível.
- **H6 (nuvens já compensadas):** exige D0 melhor que D1, D3 **e** D4. No 1018-13, D0 é pior que os três em 10 m e no
  ATE; no 1018-00, D4 é melhor que D0 em rotação e ATE. **H6 não é sustentada** pela métrica principal. Não há evidência
  do publicador.

**Resultado não explicado (registrado sem reinterpretação).** Em ambas as sequências, todas as condições com
compensação, inclusive o controle por GT (D4/D4′), pioram o RPE translacional **por quadro** em relação a D0 (1018-00
+32% a +67%; 1018-13 +21% a +83%), com piora maior nos quartis superiores de ωΔt, ao mesmo tempo em que D4 melhora o
RPE de 10 m, o ATE e o erro por 100 m. Esse comportamento não corresponde a nenhum padrão pré-registrado e a causa
permanece em aberto. Não foi verificado se os scans de D4 sem GT ao redor (167 e 135, não compensados) contribuem.

### Q2 — por que o *deskew* piorou o KISS-ICP no 1018-00 e no RELLIS

Resposta pelo protocolo: **causa não identificada.** Foram excluídos, pelos testes pré-registrados, o não
determinismo (H4), a inversão do sentido do campo `t` (D2 pior que D1) e um campo `t` incorreto como explicação
material (D3 ≈ D1, H2). H6 não é sustentada. H5 tem apenas compatibilidade parcial (rotação, 1018-00).

### RELLIS (exploratório, sem GT; `phase2/rellis_exploratory.csv`)

| Seq. | Cond. | percurso (m) | desvio-padrão do passo (cm) | divergência por quadro vs D0, t (cm) / r (°) |
|---|---|---:|---:|---|
| rellis_example (60 s) | D0 | 57,7 | 5,3 | — |
| rellis_example | D1 | 66,9 | 6,8 | 7,5 / 0,38 |
| rellis_example | D2 | 59,7 | 5,6 | 4,9 / 0,25 |
| rellis_example | D3 | 66,7 | 6,8 | 7,6 / 0,37 |
| 00000 | D0 | 342,5 | 6,0 | — |
| 00000 | D1 | 357,7 | 6,8 | 5,5 / 0,34 |
| 00000 | D2 | 358,7 | 6,7 | 5,8 / 0,33 |
| 00000 | D3 | 357,0 | 6,8 | 5,5 / 0,34 |

Cobertura 100% em todas. No trecho de 60 s, D1 e D3 percorrem 16% mais que D0, cuja distância é próxima da odometria
das rodas (~56 m, `docs/deskew_rellis.md`). No 00000, D1–D3 percorrem 4,2% a 4,7% mais que D0, sem referência
independente para decidir qual está correta. Nada disso decide configuração.

### Decisão

- Configuração do pipeline mantida: KISS-ICP com `deskew = False` (D0) nos dois datasets.
- Q1: o erro do 1018-13 está associado (correlacionalmente) aos trechos de maior velocidade e aceleração angular; H3
  permanece inconclusiva (proxies de estrutura mistos). Q2: causa em aberto.
- Em aberto, como trabalho futuro e fora deste protocolo: a piora do RPE translacional por quadro sob qualquer
  compensação, e o padrão de H1 no 1018-13 em janelas de 10 m, que exigiria pré-registro próprio.
