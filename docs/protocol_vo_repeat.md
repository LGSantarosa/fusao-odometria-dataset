# Protocolo — variabilidade entre execuções das odometrias visuais (ORB-SLAM3 e Stella VSLAM)

**Registrado em:** 16/10/2026, antes de qualquer nova execução das odometrias visuais (VOs). Até o commit deste
documento, nenhuma repetição das VOs foi executada. As execuções oficiais existentes (`data/runs/<seq>/orbslam3` e
`data/runs/<seq>/stella`, uma por sequência) já são conhecidas e não fazem parte da amostra deste protocolo.
Alterações posteriores devem ser registradas como emendas datadas, com justificativa, sem reescrever o texto original.

## 1. Objetivo

Estimar a variabilidade entre execuções do ORB-SLAM3 e do Stella VSLAM nas quatro sequências processadas, nas mesmas
condições de execução do pipeline, e decidir se cada combinação método × sequência é determinística, numericamente
equivalente ou variável. Para as variáveis, as métricas passam a ser reportadas como distribuição sobre dez execuções.

Este protocolo mede a variabilidade e não escolhe uma configuração nem uma execução. Não há critério de promoção.

## 2. Expectativa (não decide nada)

As duas VOs processam os quadros no ritmo do tempo real (`--rate 1.0`, com espera até o instante de cada quadro) e
mantêm threads de mapeamento local concorrentes ao rastreamento. A ordem de execução entre essas threads depende do
escalonamento do sistema operacional; espera-se, portanto, que as execuções não sejam determinísticas, ao contrário do
KISS-ICP (`docs/RESULTS_kissicp.md`, fase 1). A expectativa é registrada apenas como contexto; a decisão segue a regra
da seção 6, qualquer que seja o resultado.

## 3. Escopo (fixado agora, sem escolha posterior)

| Sequência | Dataset | GT | Caráter |
|---|---|---|---|
| 1018-00 | BotanicGarden | sim | confirmatório |
| 1018-13 | BotanicGarden | sim | confirmatório |
| rellis_example (trecho de 60 s) | RELLIS-3D | não (veredito C) | exploratório: só cobertura, continuidade e indicadores |
| 00000 | RELLIS-3D | não (veredito C) | exploratório: só cobertura, continuidade e indicadores |

Métodos: ORB-SLAM3 (estéreo; commit-base `4452a3c4ab75` + patches versionados em `patches/orbslam3/`) e Stella VSLAM
(estéreo; commit-base `e445b5452535` + patches versionados em `patches/stella/`), com fechamento de laço desligado nos
dois, configurações `configs/<ds>/{orbslam3,stella}.yaml` e extrações já existentes em
`data/extracted/<seq>`. Nenhuma configuração é alterada para este protocolo. Total: 8 combinações.

## 4. Condições de execução

1. Uma execução de VO por vez na máquina; nenhum outro experimento, compilação ou processo pesado em paralelo.
2. Mesmo executor do pipeline (`python -m ofd.run_vo`), com `--rate 1.0`.
3. Ordem fixa e intercalada, para não confundir repetição com deriva das condições da máquina:
   para k = 1, 2, 3 → para cada sequência na ordem 1018-00, 1018-13, rellis_example, 00000 → ORB-SLAM3, depois Stella.
   As execuções de escalonamento (seção 6) seguem a mesma intercalação, k = 4, …, 10, só nas combinações escalonadas.
4. Saídas em `data/runs/<seq>/<método>_r<k>`; logs em `data/analysis/vo_repeat/logs/`.
5. Registro por execução: commit do repositório, commit do método, SHA-256 do binário, do vocabulário, do arquivo de
   configuração e do `extract.json` da sequência; modelo da CPU e número de núcleos; carga média do sistema
   (`/proc/loadavg`) no início e no fim; duração de relógio e razão entre a duração de relógio e a duração da
   sequência; código de saída.
6. Execução malsucedida ou parcial: código de saída diferente de zero, ausência de qualquer um dos artefatos
   (`frames.csv`, `poses_causal.tum`, `state.csv`, `indicators.csv`, `run.json`) ou reprovação na verificação de
   integridade da seção 5.1. Ela é registrada e contada como resultado, com o código de saída e o motivo. Só é repetida
   se a causa for comprovadamente externa ao método (por exemplo, disco cheio), com a causa documentada; a nova
   tentativa mantém o mesmo índice k, e todas as tentativas permanecem registradas. Uma falha do próprio método (por
   exemplo, *segmentation fault*) não é substituída. Qualquer execução malsucedida ou parcial torna a combinação
   variável (seção 6).

## 5. Comparação entre execuções sem abrir métricas de erro

A comparação usa somente as saídas das próprias VOs (`poses_causal.tum`, `state.csv`, `indicators.csv`), nunca o GT.
Ela é feita entre todos os pares de execuções da combinação (3 pares com três execuções; 45 pares nas combinações
escalonadas para dez execuções). As poses são comparadas no frame nativo do
método (`cam_left`), sem extrínsecos.

### 5.1 Verificação de integridade (pré-requisito de A, B e C)

A grade canônica de cada sequência é o conjunto de instantes em `data/extracted/<seq>/images/stamps.csv`. Uma execução
é **válida** somente se:

1. tem todos os artefatos listados na seção 4, item 6, e código de saída zero;
2. `state.csv` contém exatamente os instantes da grade canônica, cada um uma única vez, sem instantes extras;
3. `indicators.csv` contém exatamente os mesmos instantes, cada um uma única vez;
4. os instantes de `poses_causal.tum` coincidem exatamente com os quadros de `state.csv` com `ok = 1`, sem duplicatas.

Uma execução inválida não é comparada: os componentes A, B e C ficam indefinidos em todos os pares que a envolvem, e
a combinação é classificada como variável. Isso impede que duas saídas igualmente truncadas sejam declaradas
determinísticas. Em execuções válidas, quadros com `ok = 0` são indisponibilidade na grade canônica e entram no
componente A; não são descartados.

### 5.2 Por que não comparar poses absolutas diretamente

Cada VO cria um novo mapa, com referencial próprio, a cada inicialização e a cada reinício após perda. Duas execuções
que inicializam em quadros diferentes, ou que reiniciam em instantes diferentes, exprimem as poses em referenciais
distintos, e a diferença absoluta mediria a escolha do referencial, não a trajetória. Um alinhamento por mínimos
quadrados também é descartado, porque absorveria parte da diferença que se pretende medir. Por isso, a comparação tem
três componentes, todos definidos sem ajuste.

### 5.3 Componente A — disponibilidade e partição em segmentos (discreta)

Sobre todos os quadros da grade canônica (seção 5.1), compara-se, entre as duas execuções:

- o vetor `ok` quadro a quadro;
- a partição em segmentos, obtida por `ofd.tracks.segments_from_state` (o mesmo critério do pipeline: novo segmento
  a cada transição de `ok` de 0 para 1 e a cada troca de `map_id`).

Resultado: "idênticos" ou não; quando não, registram-se o número de quadros com `ok` divergente, a diferença de
cobertura, de falhas e de reinícios e os instantes das fronteiras de segmento que diferem.

### 5.4 Componente B — incrementos consecutivos (contínua)

Para cada par de quadros consecutivos (i−1, i) em que as duas execuções têm `ok = 1` nos dois quadros e ambos os quadros
pertencem ao mesmo segmento em cada execução, calcula-se o incremento ΔT = T(i−1)⁻¹ T(i) em cada execução e a
diferença δ = ΔT_a⁻¹ ΔT_b. Registram-se o máximo de ‖t(δ)‖ (m) e do ângulo de rotação de δ (graus). Esse componente é
invariante ao referencial de cada mapa e corresponde ao que o dataset derivado exporta (incrementos de pose).

### 5.5 Componente C — poses ancoradas por sobreposição de segmentos (contínua)

Para cada par de segmentos (s_a da execução a, s_b da execução b) com pelo menos dois instantes comuns com `ok = 1`, toma-se
o primeiro instante comum t₀ como âncora e exprimem-se as duas trajetórias relativas a ela:
P_a(t) = T_a(t₀)⁻¹ T_a(t) e P_b(t) = T_b(t₀)⁻¹ T_b(t), para todos os instantes comuns t da sobreposição. Registra-se o
máximo, sobre t e sobre os pares de segmentos, da translação e da rotação de P_a(t)⁻¹ P_b(t). Esse componente acumula
a deriva ao longo do segmento e detecta diferenças pequenas por quadro que se somam. Quando um segmento de uma execução
se sobrepõe a dois segmentos da outra (reinício em apenas uma delas), cada sobreposição é comparada separadamente, com
âncora própria; essa situação já torna o componente A não idêntico.

### 5.6 Hashes

Calcula-se o SHA-256 de `poses_causal.tum`, de `state.csv` e de `indicators.csv` de cada execução. Os indicadores
(`inliers`, `n_features`, `reproj_err`, `tracked_ratio`) fazem parte do dataset derivado; por isso, entram na regra de
decisão pelo hash, sem limiar de tolerância.

## 6. Regra de decisão por combinação (antes de qualquer métrica de erro)

1. **Determinística:** todas as execuções são válidas (seção 5.1) e os três hashes são idênticos em todas elas → usa-se
   a execução 1, sem intervalos.
2. **Numericamente equivalente:** todas as execuções são válidas; o hash de `indicators.csv` é idêntico em todas; e,
   em todos os pares, o componente A é idêntico, B e C têm cada um ao menos uma comparação definida e os máximos de B
   e de C são menores que 1 mm e 0,01° → usa-se a execução 1 e reportam-se os máximos observados. Sem suporte
   comparável em B ou em C (nenhum par de quadros ou nenhuma sobreposição de segmentos), e com hashes diferentes, a
   combinação é variável.
3. **Variável:** qualquer outro caso, inclusive execução inválida ou indicadores diferentes com trajetória equivalente
   → a combinação é escalonada para dez execuções no total (k = 1, …, 10, mantendo as três já feitas), e todas as dez
   entram na análise. Nenhuma execução é descartada ou escolhida.

A decisão é tomada separadamente para cada uma das 8 combinações. O resultado dos componentes A, B e C é reportado em
qualquer caso, inclusive nas combinações escalonadas, como descrição da variabilidade da trajetória.

## 7. Métricas de erro e de operação (fase 2, só após revisão da fase 1)

A fase 2 só começa depois que a decisão da seção 6 for revisada e liberada. Cada execução é avaliada com as mesmas
funções do pipeline (`ofd.evaluate`), sobre a sua própria cobertura, como o dataset derivado a utilizaria:

- BotanicGarden (com GT): ATE agregado sobre os segmentos elegíveis (≥ 30 s e ≥ 20 m), RPE translacional e rotacional
  em janelas de 10 m, número de segmentos e de segmentos elegíveis, cobertura na grade LiDAR, falhas, reinícios e maior
  trecho contínuo (s e m).
- RELLIS-3D (sem GT): cobertura, falhas, reinícios, maior trecho contínuo e indicadores das VOs; nenhuma métrica de
  erro.

Estatísticas, fixadas por métrica (não escolhidas pela forma observada da distribuição):

| Métrica | Estatística principal |
|---|---|
| ATE, RPE 10 m translacional, RPE 10 m rotacional, cobertura | média e desvio-padrão amostral (n − 1) |
| falhas, reinícios, número de segmentos, número de segmentos elegíveis, maior trecho contínuo (s e m) | mediana e intervalo interquartil |
| indicadores das VOs (`inliers`, `n_features`, `reproj_err`, `tracked_ratio`) | por execução: mediana sobre os quadros com `ok = 1` e valor definido; entre execuções: média e desvio-padrão amostral dessas medianas |

Em todos os casos, reportam-se também o mínimo, o máximo e a tabela com o valor de cada execução. Os quartis são
calculados por `numpy.percentile` com interpolação linear.

Valores ausentes e métricas indefinidas:

- Indicadores: valores ausentes (vazios no CSV; `reproj_err` negativo já é convertido em ausente pelo executor) são
  excluídos da mediana da execução, e reporta-se, por execução, a fração de quadros com `ok = 1` em que cada indicador
  está ausente. Quadros com `ok = 0` não entram na mediana; seu número já é dado pela cobertura. Se um indicador
  estiver ausente em todos os quadros com `ok = 1` de uma execução, sua mediana nessa execução é indefinida; as
  estatísticas entre execuções usam somente as medianas definidas, reporta-se o número de execuções com mediana
  definida, e o desvio-padrão fica indefinido com menos de duas.
- Métricas de erro: uma métrica é indefinida numa execução quando não há suporte para ela (ATE sem segmento elegível;
  RPE sem nenhuma janela de 10 m dentro de um segmento). Para cada métrica, reporta-se o número de execuções em que ela
  está definida, e as estatísticas usam somente essas. Com menos de duas observações, o desvio-padrão fica indefinido;
  sem nenhuma, a métrica é reportada como indefinida.
- Execuções malsucedidas ou parciais (seção 4, item 6): reportam-se a taxa de sucesso da combinação (execuções válidas
  / total) e os códigos de saída. Uma execução inválida não contribui para as métricas, mas permanece no denominador
  da taxa de sucesso e na tabela por execução.

Ressalva fixada agora: como cada execução é avaliada na própria cobertura, as métricas de erro de execuções diferentes
não são pareadas; a dispersão do erro deve ser lida junto com a dispersão da cobertura e da segmentação.

## 8. Consequência para o dataset derivado

As execuções oficiais existentes continuam sendo a fonte das colunas das VOs no dataset derivado: foram produzidas antes
deste protocolo e não foram escolhidas por desempenho. As repetições não as substituem e não entram na seleção de
nenhuma execução. A métrica da execução oficial é reportada separadamente, apenas como referência, fora das
estatísticas. A decisão de incluir mais de uma execução por VO no dataset, se vier a ser considerada, exigirá registro
próprio.

## 9. Implementação e validação antes da execução

A comparação da seção 5 (componentes A, B e C, hashes e regra da seção 6) será implementada num módulo de análise e
validada apenas com dados sintéticos, cobrindo pelo menos: execuções idênticas; mesma trajetória em referenciais de
mapa diferentes (B e C nulos); perturbação conhecida de um único incremento (detectada por B e por C); deriva pequena
acumulada (detectada por C); reinício em apenas uma das execuções (A não idêntico, sobreposições comparadas
separadamente); duas execuções igualmente truncadas, com instantes duplicados ou com poses fora dos quadros `ok = 1`
(inválidas, combinação variável); trajetórias idênticas com indicadores diferentes (variável); e as estatísticas da
seção 7 com métricas indefinidas, valores ausentes e menos de duas observações. O executor das repetições registrará
os itens da seção 4. Os resultados entram em `docs/RESULTS_vo_repeat.md` (registro operacional) e no relato
acadêmico.

Estimativa de custo: como as VOs rodam em tempo real, cada rodada completa (8 combinações) leva aproximadamente a soma
das janelas de imagem das quatro sequências (96 s, 160 s, 60 s e 285 s) para os dois métodos, cerca de 20 min mais o
carregamento dos vocabulários; três rodadas, cerca de 1 h 10 min; o escalonamento de todas as combinações para dez
execuções, cerca de 2 h 40 min adicionais.

## 10. Registro de implementação — 16/10/2026 (após o registro, antes das execuções)

Esta seção registra a implementação prevista na seção 9; não altera regras, limiares nem estatísticas. Nenhuma
repetição das VOs foi executada.

- `ofd/vo_repeat.py`:
  - integridade (`validate_run`): artefatos ilegíveis, colunas obrigatórias ausentes (`ts_ns`, `ok`, `map_id` em
    `state.csv`; `ts_ns` e os quatro indicadores em `indicators.csv`), `ts_ns`, `ok` ou `map_id` não inteiros (frações
    ou ausentes, que seriam truncados ou alterariam a segmentação), `ok` fora de {0, 1}, indicadores não numéricos ou
    poses com valores não finitos tornam a execução inválida, sem interromper a análise;
  - registro externo (`read_record`): só é aceito com `status: finished` explícito e código de saída inteiro; ausente,
    ilegível (JSON inválido ou não objeto) ou incompleto (status ausente, desconhecido ou `running`, isto é, execução
    interrompida) torna a execução inválida; a situação fica gravada na coluna `record_status`;
  - componentes A, B e C (`compare_pair`); o componente A grava cobertura, quadros e instantes com `ok` divergente,
    falhas e reinícios de cada execução (mesmas definições de `ofd.evaluate.coverage`) e os instantes das fronteiras de
    segmento presentes só em uma das execuções;
  - regra da seção 6 sobre todos os pares (`analyze_combination`), que recusa classificar menos de duas execuções;
  - fase 1: `python -m ofd.vo_repeat --out data/analysis/vo_repeat/phase1` (r1–r3 em todas as combinações) e, após o
    escalonamento, `python -m ofd.vo_repeat --from-decisions data/analysis/vo_repeat/phase1/decisions.json
    --out data/analysis/vo_repeat/phase1_escalated`, que analisa r1–r10 só nas combinações variáveis e mantém r1–r3 nas
    demais;
  - estatísticas da seção 7 (`describe`) e medianas dos indicadores (`indicator_medians`).
- `ofd/run_vo_repeat.py`:
  - ordem intercalada da seção 4 sobre pares exatos (sequência, método) (`plan`); seleção por `--combos seq/método,...`
    ou `--from-decisions` (só as variáveis); sequências, métodos, combinações e repetições desconhecidos ou repetidos
    são rejeitados, e uma seleção vazia é erro;
  - execução individual de `ofd.run_vo` com `--rate 1.0`; registro por execução em
    `data/analysis/vo_repeat/logs/<seq>_<método>_r<k>.{json,log}` com commit do repositório, commit-base do método
    (`ofd.run_vo.COMMIT`) e SHA-256 de cada patch em `patches/<método>/`, CPU, número de núcleos, carga média no início
    e no fim, duração de relógio e razão sobre a duração da sequência, código de saída e SHA-256 do binário, do
    vocabulário, da configuração e do `extract.json`;
  - o registro é gravado atomicamente antes do subprocesso (`status: running`, sem código de saída) e atualizado
    atomicamente no fim (`status: finished`), de modo que uma interrupção deixa a tentativa identificada;
  - nunca sobrescreve: diretório, registro ou log existentes contam como tentativa anterior, e só se prossegue com
    `--retry-cause` (causa externa documentada, seção 4, item 6), restrito a uma única execução e recusado quando não
    há tentativa anterior; a tentativa anterior é arquivada com o sufixo `.attempt<n>` (diretório, registro e log),
    com n igual ao menor número livre, inclusive quando o registro anterior está ilegível (preservado como está e
    marcado em `previous_attempts`); o mesmo k é mantido.
- Validação sintética: `tests/test_vo_repeat.py` e `tests/test_run_vo_repeat.py` cobrem os casos da seção 9 e os
  itens acima. Em execuções idênticas, o componente C resulta em até ~10⁻¹⁵ m por arredondamento do produto inv(A)·P;
  a identidade bit a bit é decidida pelos hashes, não por C.
- Verificação de integridade aplicada às execuções oficiais existentes (já conhecidas, sem métricas de erro): as oito
  são válidas, o que confirma que a regra da seção 5.1 não reprova saídas normais do executor.
