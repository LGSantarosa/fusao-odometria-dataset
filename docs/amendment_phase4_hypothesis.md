# Emenda pré-registro — gate de desenvolvimento e reformulação da hipótese confirmatória

**Data:** 03/11/2026. **Decisão:** do autor (Luiz Santarosa), sem consulta prévia ao orientador; o orientador será
informado depois. **Referências:** `docs/PLAN_model_comparison.md` (§7.3, §7.4, Fase 4),
`docs/amendment_phase3_pilot.md` e `docs/RESULTS_phase3_pilot.md` (commit `dfa2a38`, com push antes desta emenda).

**Estado do lacre quando a decisão foi tomada:** as oito candidatas externas (`1005-00`, `1005-01`, `1005-05`,
`1005-07`, `1006-01`, `1006-03`, `1008-01`, `1008-03`) continuavam lacradas. Nenhuma feature externa foi extraída, nenhum
GT de `data/sealed` foi lido e nenhum modelo foi treinado ou aplicado fora de `1018-00` e `1018-13`.

## 1. Resultado do gate de desenvolvimento (§7.4)

O piloto formal registrou apenas a perda padronizada. Para o gate, `python -m ofd.mc_gate` refez os jobs finais das
configurações selecionadas (mesmas sementes 0–2 e orçamentos de dobra de `grid.json`, commit do executor `aaae00d`),
reproduziu a perda do piloto exatamente (diferença máxima 0,0) e calculou o RMSE vetorial em unidades físicas. Saída:
`data/analysis/model_comparison/formal_phase3/gate_dev_rmse.json`, SHA-256
`4bcea308fdcc02b86f826f268a01c4f3fa0475668b6fea9f10ff7c8298f09d9c`. Média das métricas sobre as 3 sementes.

| Modelo | Linear D-A (m/s) | Linear D-B (m/s) | Angular D-A (rad/s) | Angular D-B (rad/s) |
|---|---:|---:|---:|---:|
| B5 / T1 (`α = 1`) | 0,1549 | 0,1312 | 0,0372 | 0,0242 |
| T2 | 0,1474 | 0,1373 | 0,0370 | 0,0224 |
| F1-R / STEP | 0,1556 | 0,1363 | 0,0292 | 0,0214 |
| MLP-W | 0,1564 | 0,1388 | 0,0303 | 0,0221 |
| CNN-W (escolha temporal) | 0,1569 | 0,1383 | 0,0298 | 0,0215 |
| LSTM-W | 0,1560 | 0,1372 | 0,0289 | 0,0216 |

Melhora relativa da CNN-W, `1 − RMSE_CNN / RMSE_comparador`:

| Contraste | Linear D-A | Linear D-B | Angular D-A | Angular D-B |
|---|---:|---:|---:|---:|
| contra F1-R / STEP | −0,8% | −1,5% | −1,9% | −0,5% |
| contra B5 / T1 | −1,3% | −5,4% | +20,0% | +11,3% |
| contra MLP-W | −0,3% | +0,3% | +1,9% | +2,6% |
| contra T2 | −6,4% | −0,8% | +19,5% | +4,1% |

**Conclusão do gate:** a H1 original é **inviável**. Ela exige que o candidato temporal supere F1-R + Pα e T1/B5 + Pα
em RMSE linear e angular; no desenvolvimento, a CNN-W ficou pior que a F1-R/STEP **nas duas métricas e nas duas dobras**,
e pior que a B5 no linear nas duas dobras. A regra falharia para qualquer `δ ≥ 0`. Como H2 e H3 só seriam testadas se
H1 passasse, a hierarquia original fica sem teste confirmatório. Esse resultado negativo permanece registrado como está
e não é reinterpretado. Com `α = 1,0`, Pα não suaviza; a parte da H1 sobre "a mesma suavização" ficou sem efeito.

## 2. Nova hipótese confirmatória (H1')

**Origem declarada:** a H1' foi formulada **depois** de ver a tabela da seção 1, com base no padrão observado no
desenvolvimento (ganho angular da fusão aprendida sobre a média, sem ganho linear). Ela é testada prospectivamente nas
oito candidatas, que não participaram de nenhuma decisão. Ela **não** sustenta "temporal versus por passo"; sustenta, no
máximo, "fusão aprendida (CNN-W) versus média simples (B5)" no RMSE angular.

> **H1':** a CNN-W congelada (com Pα, `α = 1,0`, `W = 5`) reduz o RMSE angular em relação à B5/T1 nas sequências
> externas.

**Modelo:** a CNN-W, por já ter sido escolhida pela regra pré-fixada do piloto. Escolher agora a F1-R/STEP, que teve a
menor perda, seria uma seleção nova feita depois de ver os números; a LSTM-W perdeu a seleção temporal e fica fora do
teste externo.

**Regra de decisão:** para cada sequência `s`, `Δ_s = 1 − RMSE_ω(CNN, s) / RMSE_ω(B5, s)`, em que `RMSE_ω(CNN, s)` é a
média dos RMSE angulares das cinco sementes (seção 4). H1' é **positiva** somente se:

1. a mediana de `Δ_s` nas oito sequências for estritamente maior que zero; e
2. a mediana de `Δ_s` for estritamente maior que zero separadamente em `1005` (4 sequências), `1006` (2) e `1008` (2);
   com duas sequências, a mediana é a média das duas; e
3. o RMSE angular estiver definido para a CNN e para a B5 nas oito sequências. Se faltar alguma, H1' fica
   **indeterminada**, não positiva.

`δ_ω = 0`: a hipótese é direcional, sem alegação de relevância prática. Não há valor-p confirmatório. A dependência
entre sequências do mesmo dia é tratada pela exigência por dia (três blocos); a contagem de sequências favoráveis é
reportada só como descritiva e não substitui a regra.

## 3. Guardas descritivas

Não há base independente para uma margem de não inferioridade no RMSE linear nem no RPE de 10 m: qualquer margem
fixada agora seria escolhida depois de ver os valores da seção 1. Por isso, e **não** porque uma margem específica
falharia, as guardas passam a ser descritivas:

- o RMSE linear e o RPE de 10 m não entram na decisão de H1';
- ambos são reportados obrigatoriamente por sequência, por dia e agregados, para CNN-W, B5, F1-R/STEP, MLP-W e T2;
- a conclusão declara o custo sem suavizar, na forma "melhora angular de X% ao custo de Y% no linear e Z% no RPE"
  (ou o ganho, se houver);
- ficam proibidas as expressões "melhor modelo", "superioridade geral" e "sem degradação". A alegação se limita ao RMSE
  angular contra a B5.

## 4. Comparações descritivas, sementes e modelos finais

- **Descritivas:** F1-R/STEP, MLP-W e T2 (com as escolhas do piloto), todos contra a B5 e entre si, nas duas métricas,
  por sequência e por dia. H2 e H3 do plano não são testadas.
- **Sementes:** modelos finais com as sementes 0 a 4. Para cada modelo e sequência, calcula-se a métrica de cada
  semente e reporta-se a **média das métricas** (mesmo critério da seleção no piloto). Não há ensemble de predições:
  ele favoreceria apenas o lado treinado do contraste contra a B5. O desvio entre sementes é reportado, mas não é usado
  na decisão.
- **Treino final:** CNN-W, F1-R/STEP e MLP-W treinados em `1018-00` e `1018-13` juntos, com as configurações
  selecionadas no piloto, sem validação nem parada antecipada, pelo orçamento final da emenda da fase 3 (mediana,
  arredondada para cima, dos dois orçamentos de dobra): STEP 3.300, MLP-W 500, CNN-W 1.800 atualizações. T2 usa
  `q_scale = 1`, `r_scale = 0,3`, com covariâncias estimadas nas duas sequências de desenvolvimento.
- **Congelamento:** antes de qualquer inferência externa, cada modelo é gravado como artefato versionado
  (normalizador, cinco `state_dict`, configuração, sementes, orçamento e SHA-256) e registrado em `PREDICTORS` de
  `ofd/blind.py`, em commit com push. Só depois disso pode rodar o job cego único nas oito.

## 5. Ordem a partir desta emenda

1. Commit e push desta emenda e de `ofd/mc_gate.py`.
2. Treino final, artefatos e `PREDICTORS`; commit e push.
3. Job cego único nas oito, auditoria dos manifestos e abertura única (G1).
