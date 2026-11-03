# Emenda pré-piloto formal — fase 3 do estudo de comparação de arquiteturas

**Data:** 03/11/2026. **Decisão:** do autor (Luiz Santarosa), sem consulta prévia ao orientador; o orientador será
informado depois. **Referência:** `docs/PLAN_model_comparison.md`, §9, Fase 3.

Esta emenda fixa os valores do piloto formal da fase 3. O piloto usa somente `1018-00` e `1018-13`; as oito candidatas
permanecem lacradas e nenhum resultado externo é autorizado. O SHA-256 deste arquivo e o commit que o registrou são
gravados no manifesto do piloto formal (`data/analysis/model_comparison/formal_phase3/manifest.json`), e o executor
(`ofd/mc_pilot.py`) recusa iniciar se o arquivo tiver alterações não registradas.

## 1. Declaração do piloto provisório já observado

Um piloto provisório (`ofd/mc_pilot.py`, commit `53e46eb`) foi executado em 30/10/2026, **antes** desta emenda, contra a
ordem combinada (emenda e concordância antes de qualquer piloto). Ele usou só os dados de desenvolvimento, não leu
`data/sealed` e seus artefatos estão preservados em `data/analysis/model_comparison/provisional_phase3/`, marcados como
`PROVISIONAL_DEVELOPMENT_PILOT`. Ele **não** é adotado: o piloto formal é refeito do zero em raiz nova, sem reaproveitar
nenhum artefato provisório.

Resultados vistos pelo autor no piloto provisório:

- grade de `α` executada {0,1; 0,2; 0,5; 1,0} (sem 0,3 e 0,7). Perda da B5 + Pα decrescente em `α`: 0,837; 0,730;
  0,525; 0,396. Escolhido `α = 1,0`, no limite da grade (Pα sem suavização);
- `W` com a MLP-W de referência: perda 0,381 (W = 5), 0,411 (W = 10), 0,393 (W = 20). Escolhido `W = 5`, no limite
  inferior da grade;
- grade de 18 configurações por família, com `α = 1,0` e `W = 5`: melhores perdas STEP 0,351; LSTM 0,360; CNN 0,363;
  MLP-W 0,365. Escolha temporal: CNN (empate em 1% com a LSTM, menos parâmetros);
- T2: `q_scale = 1`, `r_scale = 0,3` (perda 0,404).

Decisões influenciadas: nenhuma grade, limiar ou regra de seleção foi alterada por causa desses resultados. A única
mudança no executor depois do piloto provisório foi incluir 0,3 e 0,7 na grade de `α` (commit `029e9a2`), valores que já
constavam do rascunho escrito antes da execução. Em particular, as grades de `α` e `W` **não** foram estendidas além dos
limites atingidos (`α > 1` não tem sentido para a EMA; `W < 5` não foi considerado). Como os resultados do piloto provisório
foram vistos antes, o piloto formal continua exploratório no sentido do plano (§9, Fase 3): fixa decisões e capacidade
para a fase 4, mas não é apresentado como confirmação.

## 2. Valores aprovados (dúvidas que estavam em aberto)

- **`E_gt`:** calculado na sequência de treino de cada dobra, por componente do alvo. Para cada componente, é o menor
  `L ≤ 50` tal que `|ρ(l)| < 0,2` para todo `l` em `[L, 50]`. `ρ(l)` é a correlação de Pearson entre `y_t` e `y_{t+l}`
  nos pares com os dois valores finitos, indefinida com menos de 3 pares ou variância nula; ρ indefinida não conta como
  abaixo do limiar. Se nenhum `L` satisfaz a condição, `L = 50` (fallback conservador). `E_gt` é o máximo entre as
  componentes. Nas duas sequências de desenvolvimento, `gt_vx` não satisfaz a condição até 50, então `E_gt = 50`.
- **Embargo máximo:** `E_antes = max(E_gt, R + M_α)`, `E_depois = max(E_gt, R)`, `R = W + 9`, `M_α` com `ε = 0,01`. A
  fração consumida pelos embargos em uma subdobra é limitada a 25% do total de linhas da sequência de treino da dobra
  LOSO. Valores de `α` ou `W` que excedam o limite são rejeitados antes de qualquer métrica. No pior caso (`α = 0,1`,
  `W = 20`, `E_gt = 50`), a fração é 8,4% (`1018-00`) e 5,9% (`1018-13`).
- **`W`:** candidatos {5, 10, 20}, escolhidos com uma MLP-W fixa (largura 32, uma camada, `weight_decay = 1e-3`). Perda
  após Pα agregada nas duas dobras e nas 3 sementes; empate quando a perda ≤ 1,01 × a mínima, favorecendo o menor `W`.

## 3. Ordem de seleção (sequencial, toda no LOSO D-A/D-B)

1. `α` com B5: grade {0,1; 0,2; 0,3; 0,5; 0,7; 1,0}; `α_min = 0,1`. Perda média das duas dobras; empate (≤ 1,01 × a
   mínima) → maior `α` (menor memória). Congelar Pα.
2. `W` como na seção 2. Congelar `W`.
3. Com `α` e `W` congelados: grade de 18 configurações por família (F1-R/STEP, MLP-W, CNN-W, LSTM-W). Em cada família e
   na escolha CNN versus LSTM: empate (≤ 1,01 × a mínima) → menos parâmetros; persistindo, menor perda. A latência não
   entra no desempate do piloto.
4. T2: grade própria, escolhida só no LOSO; empate (≤ 1,01 × a mínima) → escalas mais próximas de 1 (`|log10 q|`,
   depois `|log10 r|`).

## 4. Grades, orçamento e sementes

- STEP (F1-R) e MLP-W: largura {16, 32, 64} × camadas {1, 2} × `weight_decay` {1e-4, 1e-3, 1e-2};
- CNN-W: canais {16, 32, 64} × camadas {1, 2} × `weight_decay` {1e-4, 1e-3, 1e-2}, kernel 3, preenchimento causal;
- LSTM-W: oculto {16, 32, 64} × camadas {1, 2} × `weight_decay` {1e-4, 1e-3, 1e-2}, estado zero em cada janela;
- teto de 100 mil parâmetros, como proteção (a maior configuração tem cerca de 76,3 mil).

**Orçamento:** Adam, `lr = 1e-3`, lote 64, máximo de 8.000 atualizações em todas as famílias. Checkpoints em 50, 100 e
200 atualizações e depois a cada 200, até 8.000. O melhor orçamento é o checkpoint de menor perda após Pα (empate → menos
atualizações). Se o melhor for o último checkpoint, usa-se 8.000 sem extensão; o caso é marcado como saturado e
reportado, e o máximo não é ampliado depois de observar o piloto. Orçamento da dobra: mediana, arredondada para cima, dos
melhores orçamentos sobre blocos internos e sementes. Orçamento final: mediana, arredondada para cima, dos dois
orçamentos de dobra.

**T2:** `q_scale` {0,1; 0,3; 1; 3; 10} × `r_scale` {0,3; 1; 3}. Os escalares multiplicam covariâncias diagonais
estimadas exclusivamente na sequência de treino: `R_m` é a variância de (twist_m − alvo) nas linhas válidas e `Q` é a
variância da diferença do alvo entre linhas consecutivas, ambas com piso numérico de 1e-12 antes da escala. A
inicialização usa a primeira medida válida com variância `r_scale · R_m`; antes dela, a saída é zero.

**Sementes:** 3 sementes no CV do piloto. Qualquer execução falha torna a configuração inelegível.

## 5. Fora do piloto (fase 4)

`δ_v`, `δ_ω`, `δ_RPE`, 5 sementes nos modelos finais e combinação de sementes no teste, aumento por remoção de fontes e
regra de `k`.
