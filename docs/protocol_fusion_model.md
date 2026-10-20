# Protocolo — modelo de fusão das odometrias

**Registrado em:** 19/10/2026, antes de qualquer treinamento, ajuste ou predição de modelo de fusão. A base é o dataset
`dataset-v1.0.0` (commit `d4a9c48`, manifesto `docs/dataset_manifest.json`). Alterações posteriores devem ser
registradas como emendas datadas, com justificativa, sem reescrever o texto original.

## 1. Objetivo e pergunta

Estimar, a cada passo da grade LiDAR, a velocidade do veículo em se(3) (`gt_vx … gt_wz`) a partir das quatro odometrias
(ORB-SLAM3, Stella VSLAM, FAST-LIO, KISS-ICP) e dos seus indicadores de qualidade, e medir se essa fusão **generaliza
para um percurso não visto** melhor do que as odometrias isoladas e do que fusões simples.

Pergunta confirmatória (seção 9): um modelo que aprende a ponderar as fontes supera, na sequência não vista, o melhor
baseline escolhido sem acesso a ela?

## 2. O que já é conhecido (não decide nada)

- As métricas de cada odometria isolada nas duas sequências com GT já foram calculadas e consultadas
  (`data/output/metrics.csv`, `docs/RESULTS_kissicp.md`, `docs/RESULTS_vo_repeat.md`). Por isso, famílias de modelo,
  grades de hiperparâmetros e regras de escolha são fixadas aqui e não podem ser ajustadas depois de ver os resultados
  do modelo.
- As VOs são variáveis entre execuções (`docs/RESULTS_vo_repeat.md`); o dataset usa uma única realização (a execução
  oficial).
- Contagens descritivas (sem erro), por sequência:

| Sequência | Linhas | Com GT | Duração (s) | Linhas com GT por nº de fontes válidas (1 / 2 / 3 / 4) |
|---|---:|---:|---:|---|
| 1018-00 | 1466 | 1299 (um trecho contínuo) | 147,8 | 198 / 148 / 0 / 953 |
| 1018-13 | 2071 | 1936 (um trecho contínuo) | 208,8 | 121 / 232 / 34 / 1549 |
| rellis_example | 599 | 0 | 59,8 | — |
| 00000 | 2849 | 0 | 284,8 | — |

Nenhuma linha com GT tem zero fontes válidas (o KISS-ICP é válido em 1465/1466 e 2070/2071 linhas).

## 3. Dados, entradas e alvo

- **Entradas:** as 56 colunas com papel `feature` em `data/output/schema.json` (por método: `vx … wz`, `valid`,
  `dt_ms`, `age_ms`, os quatro indicadores e a variância móvel causal). Nenhuma outra coluna entra no modelo; colunas
  `metadata`, `target` e `evaluation` nunca são entrada (`ofd.schema.assert_no_leak`).
- **Alvo:** `gt_vx, gt_vy, gt_vz` (m/s) e `gt_wx, gt_wy, gt_wz` (rad/s), no frame do LiDAR.
- **Linhas usadas:** treino, validação e métricas usam somente as linhas com o alvo definido (as 6 componentes
  finitas). Essa regra depende só da disponibilidade do GT, não do desempenho. O modelo produz predição em todas as
  linhas da grade (necessário para a integração da seção 8).
- **Leitura:** Parquet (formato canônico); nada é lido do CSV.

## 4. Divisão dos dados

1. **Avaliação externa — leave-one-sequence-out:** dobra A treina em 1018-00 e testa em 1018-13; dobra B treina em
   1018-13 e testa em 1018-00. Nenhuma divisão aleatória por linhas.
2. **Validação interna — blocos temporais, só na sequência de treino:** as linhas com GT da sequência de treino são
   divididas em 5 blocos contíguos de tamanho igual (o último absorve o resto). Na subdobra j, o bloco j é a
   validação e os demais são treino, com **purga de 10 linhas** de cada lado do bloco de validação (a janela H = 10 da
   variância móvel causal; evita que linhas de treino compartilhem histórico com a validação).
3. **Ajustes só no treino:** normalização, imputação, escolha de hiperparâmetros, número de épocas e escolha do
   melhor baseline são calculados exclusivamente com as linhas de treino da subdobra (validação interna) ou da
   sequência de treino (modelo final). A sequência de teste não é lida até a fase 2 (seção 12).
4. **RELLIS-3D:** somente inferência exploratória (seção 10), sem seleção de modelo, sem métricas de erro.

## 5. Pré-processamento (ajustado no treino, aplicado igual em validação e teste)

- **Padronização das entradas:** média e desvio-padrão por coluna, calculados nas linhas de treino em que a coluna
  está definida. Para as colunas de um método, só as linhas com `valid = 1` desse método. Casos especiais:
  - `valid` permanece binário (0/1), sem padronização;
  - coluna com desvio-padrão zero no treino usa escala 1 (só é centrada);
  - coluna sem nenhum valor definido nas linhas de treino torna inválida a subdobra (validação interna) ou o modelo
    final daquela dobra, que é registrado como falha (seção 7), em vez de produzir NaN.
- **Clipe (emenda de 20/10/2026, seção 14):** após a padronização, toda entrada padronizada é limitada ao intervalo
  [−10, 10]. O clipe é aplicado igualmente em treino, validação, teste e inferência exploratória, antes da imputação
  de valores ausentes por 0. Colunas `valid` permanecem binárias e a regra "desvio zero → escala 1" é mantida.
- **Imputação neutra:** depois da padronização, todo valor ausente (método inválido, indicador ausente, variância
  móvel ainda sem janela) vira 0, isto é, a média de treino. A coluna `valid` de cada método permanece entre as
  entradas e informa a ausência. Nenhuma linha ou coluna é removida por ter valores ausentes.
- **Padronização do alvo:** cada componente do alvo é dividida pelo seu desvio-padrão σ_c nas linhas de treino (sem
  centrar; σ_c = 0 usa escala 1). É essa escala que fixa o peso relativo entre translação e rotação na perda
  (seção 7).
- **Desvio-padrão:** todas as médias e desvios-padrão das entradas e do alvo usam o desvio-padrão populacional
  (ddof = 0).

## 6. Modelos

### 6.1 Baselines (sem aprendizado, salvo B6)

- **B1–B4 — odometria isolada:** o twist do método (`m_vx … m_wz`). Em linhas com o método inválido, repete-se a
  última predição válida (retenção causal); antes da primeira linha válida, a predição é zero.
- **B5 — média das válidas:** média simples dos twists dos métodos com `valid = 1` na linha; sem nenhuma válida,
  retenção causal.
- **Bsel — melhor odometria isolada escolhida no treino:** entre B1–B4, a de menor perda média na validação interna
  da sequência de treino (seção 7). É o baseline principal da seção 9. Escolhê-la pelo teste seria vazamento.
- **B6 — regressão ridge:** linear das 56 entradas padronizadas para o alvo padronizado, com intercepto não
  penalizado (`fit_intercept=True`) e solução fechada determinística.

### 6.2 Modelos de fusão

- **F1 — ponderação aprendida (modelo principal):** uma rede (MLP) recebe as 56 entradas padronizadas e produz quatro
  logits, um por método. Os logits dos métodos inválidos na linha são mascarados (−∞), e a softmax dá pesos que somam
  1. A predição é a média ponderada dos twists dos métodos válidos. Como os pesos são não negativos, F1 só seleciona e
  pondera fontes, o que torna o resultado interpretável. Sem nenhuma fonte válida, retenção causal.
- **F2 — regressão direta (comparação):** MLP das 56 entradas padronizadas para o alvo padronizado, sem restrição.

Os modelos são **por passo**: usam só a linha k (que já carrega o histórico causal na variância móvel). Nenhum modelo
sequencial é avaliado neste protocolo.

## 7. Treinamento, perda e hiperparâmetros

- **Perda:** L = média sobre linhas e sobre as 6 componentes de ((ŷ_c − y_c) / σ_c)², com y e ŷ em unidades físicas
  (m/s, rad/s) e σ_c da seção 5. A escala relativa entre translação e rotação é, portanto, a razão entre os
  desvios-padrão de treino de cada componente; nenhum peso adicional é escolhido depois. Fluxo por família:
  - F1 e B1–B5 produzem a predição diretamente em m/s e rad/s (combinação dos twists físicos dos métodos); o erro é
    dividido por σ_c só no cálculo de L;
  - F2 e B6 predizem no espaço padronizado (ŷ_c / σ_c); a predição é multiplicada por σ_c antes das métricas e da
    integração (seção 8); em treino, L coincide com o erro quadrático médio no espaço padronizado;
  - Bsel compara B1–B4 por exatamente essa L, calculada na validação interna.
- **Otimização (F1, F2):** Adam, taxa de aprendizado 1e-3, lotes de 64 linhas embaralhadas dentro do treino, ativação
  ReLU, até 500 épocas.
- **Grades fixadas:**

| Família | Hiperparâmetros | Configurações |
|---|---|---:|
| B6 | α ∈ {1e-3, 1e-2, 1e-1, 1, 10, 100, 1000} | 7 |
| F1, F2 | largura ∈ {16, 32, 64} × camadas ocultas ∈ {1, 2} × decaimento de peso ∈ {1e-4, 1e-3, 1e-2} | 18 cada |

- **Número de épocas:** na validação interna, registra-se a época de menor perda de validação em cada subdobra e
  semente; o modelo final é treinado em toda a sequência de treino pelo número de épocas igual à mediana dessas épocas
  (arredondada para cima). Não há parada antecipada no modelo final.
- **Sementes:** validação interna com as sementes 0, 1 e 2; modelo final com as sementes 0 a 4. A semente controla
  inicialização e embaralhamento.
- **Regra de escolha (por família e por dobra):** a configuração de menor perda média de validação sobre as 5
  subdobras e as 3 sementes. Empate: toda configuração com L ≤ 1,01 × L_min, sendo L_min a menor perda média da
  família; entre elas, escolhe-se a mais simples (menos parâmetros; persistindo, maior decaimento de peso ou maior α).
  Entre famílias não há escolha: todas são avaliadas no teste e reportadas.
- **Falhas de treinamento:** perda não finita em qualquer época = execução falha. Na validação interna, uma
  configuração com qualquer execução falha recebe perda infinita (não é escolhida). No modelo final, a semente falha é
  registrada e contada, sem substituição; as estatísticas usam as sementes restantes, e reporta-se quantas falharam.

## 8. Integração causal do twist previsto

O twist previsto na linha k, ξ̂_k = (v̂_k, ω̂_k), cobre o intervalo da grade (t_{k−1}, t_k], como o alvo. A pose é
integrada causalmente:

```latex
\hat T_k = \hat T_{k-1}\,\exp\!\big(\hat\xi_k^{\wedge}\,\Delta t_k\big), \qquad \Delta t_k = t_k - t_{k-1}
```

Índices: a primeira linha do trecho com GT é k = 0, com T̂_0 = I; o primeiro twist aplicado é o da linha k = 1, que
cobre (t_0, t_1]. O twist da linha 0 não entra na integração (cobre um intervalo anterior ao trecho). A trajetória do
GT é integrada da mesma forma a partir de `gt_vx … gt_wz`, o que torna as duas trajetórias comparáveis por
construção. Nenhuma pose futura é usada.

## 9. Métricas e regra de decisão

Todas as métricas são calculadas na sequência de teste, nas linhas com GT, por dobra, por modelo e por semente.

**Primárias:**

- RMSE translacional da velocidade: √(média ‖v̂ − v‖²), em m/s;
- RMSE rotacional da velocidade: √(média ‖ω̂ − ω‖²), em rad/s (reportado também em °/s).

**Secundárias:**

- RPE em janelas de 10 m (translação em m, rotação em rad) e ATE após alinhamento SE(3) sobre todo o trecho, ambos
  sobre as trajetórias da seção 8, com as funções de `ofd.evaluate` (`rpe`, `segment_metrics`/`aggregate_ate`, com o
  trecho inteiro como um segmento);
- RMSE por componente (6);
- métricas primárias estratificadas pelo número de fontes válidas na linha (1, 2, 3, 4), cada estrato com o seu n;
  com n = 0 (o estrato de 3 fontes no 1018-00, por exemplo), as métricas do estrato são indefinidas. Os estratos são
  só descritivos e não entram na regra de decisão;
- F1: peso médio de cada método, global e por estrato.

**Estatísticas:** para F1 e F2, por dobra, média e desvio-padrão amostral sobre as sementes, mínimo e máximo; tabela
por semente. B1–B5, Bsel e B6 (ridge, solução fechada) são determinísticos: um único valor por dobra, sem sementes.

**Regra de decisão (pré-registrada):** "F1 supera os baselines" somente se, **nas duas dobras** e **nas duas métricas
primárias**, a média de F1 sobre as sementes for menor que o valor de Bsel e que o valor de B6, com diferença maior
que duas vezes o desvio-padrão de F1 entre sementes. Em qualquer outro caso, o resultado é registrado como negativo ou
inconclusivo, sem reinterpretação. A mesma regra é aplicada a F2, como comparação. As secundárias descrevem; não
decidem.

**Métricas indefinidas:** o RPE de 10 m é indefinido se não houver nenhuma janela de 10 m; reporta-se o número de
sementes em que cada métrica está definida, e as estatísticas usam só as definidas. Se uma métrica primária ficar
indefinida em alguma dobra, a regra de decisão não pode ser satisfeita.

## 10. RELLIS-3D (exploratório)

Os modelos finais das duas dobras (sementes 0–4) são aplicados a rellis_example e 00000, com o pré-processamento
ajustado na respectiva sequência de treino. Reportam-se só descrições: distribuição das velocidades previstas, peso
médio por método (F1) e concordância entre os modelos das duas dobras. Nenhuma métrica de erro, nenhuma escolha. A
mudança de domínio (outros sensores, câmera a 7,5 Hz) é declarada como limitação.

## 11. Artefatos e tabelas obrigatórios

Em `data/analysis/fusion/` (fora do git):

- `phase1/<dobra>/cv.csv`: família, configuração, subdobra, semente, perda de validação, melhor época, falha;
- `phase1/<dobra>/selected.json`: configuração escolhida por família, número de épocas, baseline Bsel, estatísticas
  de normalização; congelado ao fim da fase 1;
- `phase2/test_metrics.csv`: dobra, modelo, semente, métricas primárias e secundárias, falha;
- `phase2/stratified.csv`, `phase2/weights_f1.csv`;
- `phase2/predictions/<dobra>_<modelo>_s<semente>.parquet`: `t`, twist previsto e, para F1, pesos;
- `phase2/rellis/…`: predições e descrições da seção 10.

Registro em `docs/RESULTS_fusion_model.md` (tabelas por dobra: primárias com média ± desvio, regra de decisão aplicada,
secundárias, estratos, pesos) e no relato acadêmico.

## 12. Fases e liberações

1. **Fase 0 — implementação e validação sintética.** Módulo de treino e avaliação validado só com dados sintéticos:
   divisão em blocos com purga; pré-processamento ajustado só no treino (teste de que valores do bloco de validação
   ou do teste não alteram as estatísticas); máscara e softmax de F1 (pesos nulos em métodos inválidos); retenção
   causal; integração da seção 8 (recupera a trajetória do GT a partir do próprio twist do GT, com T̂_0 = I e o
   primeiro twist aplicado sendo o da linha 1); `valid` sem padronização, coluna de desvio zero com escala 1 e coluna
   sem valor definido tratada como falha; perda L idêntica para F1/B1–B5 (espaço físico) e F2/B6 (espaço
   padronizado); estratos vazios indefinidos; regra de escolha;
   falhas; métricas indefinidas. Nenhum dado real de alvo é lido. Revisão antes da fase 1.
2. **Fase 1 — validação interna.** Para cada dobra, só a sequência de treino é lida; gera `cv.csv` e
   `selected.json`. Nenhuma métrica na sequência de teste. Revisão e liberação separada antes da fase 2.
3. **Fase 2 — teste e RELLIS.** Modelos finais, métricas da seção 9, regra de decisão, seção 10. Registro sem
   reinterpretação.

## 13. Limitações declaradas

- Só duas sequências com GT (≈130 s e ≈194 s), do mesmo dataset: a generalização medida é entre dois percursos,
  não entre ambientes ou sensores.
- As VOs são variáveis entre execuções, e o dataset usa uma única realização; a sensibilidade do modelo a essa
  variabilidade não é medida aqui.
- A divisão do twist por dt amplifica o ruído em intervalos curtos; `dt_ms` está entre as entradas para que o modelo
  possa identificá-los.
- O KISS-ICP é válido em quase todas as linhas; os estratos com 1–3 fontes válidas são pequenos (seção 2).
- Modelos por passo não exploram dinâmica temporal além da variância móvel causal.

## 14. Registro de implementação da fase 0 — 19/10/2026 (após a liberação, antes da fase 1)

Esta seção registra a implementação liberada em 19/10/2026; não altera regras, grades nem estatísticas. Nenhum alvo
real foi lido, nenhuma validação interna foi executada e nenhum modelo foi treinado com dados do dataset.

- Ambiente: PyTorch 2.14.1 só CPU (`requirements.lock`, índice em `scripts/setup_env.sh`), redes em float64,
  `torch.use_deterministic_algorithms(True)`; a semente fixa inicialização e embaralhamento.
- `ofd/fusion_data.py` (seções 3–5): `FEATURES` (as 56 colunas `feature` do schema), `TARGET`, `target_rows`, `blocks`
  (5 blocos, purga de 10), `Standardizer` (ddof = 0, `valid` binário, desvio zero → 1, coluna vazia →
  `EmptyColumnError`, ausentes → 0), `target_sigma`, `method_twists`, `n_valid`.
- `ofd/fusion_models.py` (seções 6–7): perda L em unidades físicas divididas por σ, retenção causal, B1–B5, ridge
  com intercepto não penalizado (solução fechada), F1 (softmax mascarada) e F2, `train_nn` (Adam com
  `weight_decay`, lr 1e-3, lotes de 64, sem parada antecipada), contagem de parâmetros.
- `ofd/fusion_eval.py` (seções 7–9): integração (T̂₀ = I, primeiro twist = linha 1), métricas primárias, por
  componente e secundárias (`ofd.evaluate.rpe`, `segment_metrics`, `aggregate_ate`), estratos, agregação da validação
  interna (falha → perda infinita), escolha (empate L ≤ 1,01 L_min, depois simplicidade), épocas finais, regra de
  decisão.
- `ofd/fusion_run.py` (seções 4, 10–12): `phase1` recebe só a sequência de treino da dobra e grava `cv.csv` e
  `selected.json`; `phase2` só aceita seleção congelada completa e grava `test_metrics.csv`, `stratified.csv`,
  `weights_f1.csv`, `predictions/` e `decision.json` (F1 e, como comparação, F2); `rellis_inference` grava
  `describe.csv` e `agreement.csv`, sem métricas de erro. CLI: `python -m ofd.fusion_run phase1 --fold A|B` e
  `python -m ofd.fusion_run phase2`.
- Validação sintética: `tests/test_fusion_data.py`, `tests/test_fusion_models.py`, `tests/test_fusion_eval.py`,
  `tests/test_fusion_run.py` (43 testes; dados de `tests/fusion_synth.py`), cobrindo a lista da seção 12, item 1.
  Suíte: 279 testes.
- Custo medido em dado sintético do tamanho real (~1030 linhas de treino, 500 épocas): 10–14 s por treinamento;
  a fase 1 tem 540 treinamentos por dobra (~1,7 h por dobra em série).
- Pontos de interpretação para a revisão (escolhas de implementação onde o texto admite leituras diferentes):
  1. Perda de validação de uma execução de rede = a menor perda de validação entre as épocas (a da melhor época,
     que também define o número de épocas do modelo final).
  2. Na validação interna, B1–B5 são calculados sobre a sequência de treino inteira e depois recortados no bloco de
     validação: a retenção causal pode usar linhas anteriores ao bloco (só entradas, nunca o alvo).
  3. Em F1, linhas sem nenhuma fonte válida ficam fora do gradiente (nenhum parâmetro as afeta); na predição, recebem
     retenção causal. Nas sequências com GT não há linhas assim (seção 2).
  4. "Decaimento de peso" = o `weight_decay` do Adam do PyTorch (penalidade L2 somada ao gradiente), não AdamW.
  5. Empate exato entre odometrias isoladas na escolha de Bsel → a primeira na ordem ORB-SLAM3, Stella, FAST-LIO,
     KISS-ICP.
  6. A fase 2 recusa uma sequência de teste cujas linhas com GT não formem um único trecho contínuo (seção 8); as
     duas sequências têm um único trecho.
  7. Pesos de F1 reportados globalmente e por estrato; no RELLIS, além das descrições, a diferença RMS entre as
     predições dos modelos das duas dobras (`agreement.csv`).
- Revisão de 19/10/2026: as sete escolhas acima foram aceitas; três ajustes, todos com teste:
  (a) perda de validação não finita marca a execução como falha (antes só lote e treino);
  (b) as predições do RELLIS são gravadas em `phase2/rellis/predictions/<dobra>_<sequência>_<modelo>_s<semente>.parquet`
  (com os pesos, em F1);
  (c) `selected.json` registra `fold` e `train_sequence`, e a fase 2 (e a inferência no RELLIS) recusa seleção de
  outra dobra, sequência de treino diferente da registrada ou sequência de teste igual à de treino.
  Suíte: 281 testes.
- Fase 1 executada em 19/10/2026 com `3c34457` e **invalidada** (`docs/RESULTS_fusion_model.md`): linhas com o
  método inválido não recebiam 0 em `dt_ms`, `age_ms` e na variância móvel, que no dataset trazem valores antigos
  (seção 5 violada). Correção em `Standardizer.transform`, com teste; artefatos preservados em
  `data/analysis/fusion/phase1_invalid_3c34457/`. Lacuna registrada para decisão: colunas quase constantes no treino
  (escala positiva, mas muito pequena) produzem valores padronizados extremos, e a seção 5 só trata desvio zero.
- **Emenda de 20/10/2026 (antes de repetir a fase 1): clipe das entradas padronizadas em ±10** (seção 5). Motivo: na
  subdobra 4 da dobra B (treino 1018-13), o par de jitter dominante de `kissicp_dt_ms` e `fastlio_dt_ms` (98,34 e
  103,42 ms, linhas 1677–1678) cai inteiro no bloco de validação; com desvio de treino de ≈ 0,0016 ms, as entradas
  chegam a ≈ 1636σ (desvios menores nas linhas 1669, 1670 e 1676 chegam a ≈ 35,6σ). Nas subdobras 0–3 o desvio
  de `kissicp_dt_ms` fica entre 0,09156 e 0,09186 ms, e no ajuste final é 0,08164 ms (máximo 31,32σ); `fastlio_dt_ms`
  é semelhante. Na dobra A o maior valor nos blocos de validação é ≈ 61σ (`orbslam3_n_features`). No ajuste final,
  o limite 10 afeta 28 células na dobra A e 70 na B, inclusive alguns extremos legítimos: é uma salvaguarda geral,
  não um conserto só de `*_dt_ms`. Alternativas descartadas: manter o texto (seleção da dobra B dependente de 5
  linhas); escala mínima por coluna (exige escolher ε por tipo de coluna); remover `*_dt_ms` (muda as 56 entradas);
  a simples substituição por MAD ou IQR não resolve, pois ambas podem zerar numa coluna quantizada e exigiriam uma
  regra adicional. **Origem da decisão:** a decisão foi informada pela inspeção das entradas das sequências de
  treino da fase 1 invalidada, incluindo seus blocos internos de validação; nenhuma perda, época, configuração
  selecionada ou métrica de teste foi usada para escolher k, e nenhum outro valor de k foi testado. Implementação:
  `CLIP` em `ofd/fusion_data.py`, aplicado em `Standardizer.transform`; teste
  `tests/test_fusion_data.py::test_standardized_inputs_are_clipped_after_imputation_rules` (os dois sinais, zeros
  imputados e colunas `valid` preservados; falha sem o clipe). Suíte: 283 testes. Revisão: aprovada (Codex).
