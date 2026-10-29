# Plano de estudo — comparação de arquiteturas para fusão de odometrias

> **RASCUNHO REVISADO — 29/10/2026.** Documento atualizado após revisão externa e verificação do pipeline. Ainda não
> é um protocolo pré-registrado, não autoriza abrir novas sequências de teste e não altera o experimento concluído em
> `docs/protocol_fusion_model.md`. A triagem do parecer está em
> `docs/REVIEW_RESPONSE_model_comparison_2026-10-29.md`,
> `docs/REVIEW_RESPONSE_model_comparison_2026-10-29_r2.md`,
> `docs/REVIEW_RESPONSE_model_comparison_2026-10-29_r3.md` e
> `docs/REVIEW_RESPONSE_model_comparison_2026-10-29_r4.md` e
> `docs/REVIEW_RESPONSE_model_comparison_2026-10-29_r5.md`. Os bloqueios G0–G3 abaixo precisam ser resolvidos antes
> do novo protocolo.

## 1. Ideia e escopo do artigo

Pergunta confirmatória proposta:

> Em percursos não vistos, o uso explícito de histórico causal reduz o erro da fusão além do que se obtém com a
> ponderação por passo e com uma suavização temporal causal sem aprendizado?

O artigo deverá manter duas análises distintas:

1. **Fontes, descritiva:** ORB-SLAM3, Stella VSLAM, FAST-LIO2 e KISS-ICP isoladamente, média das válidas, cobertura e
   continuidade.
2. **Modelos, confirmatória se houver dados:** MLP por passo, baseline temporal clássico, MLP com janela e um encoder
   causal escolhido entre CNN 1D e LSTM. Cabeça direta, ablações e BiLSTM ficam exploratórias.

O primeiro experimento já comparou as quatro odometrias, a média, ridge e duas MLPs. O novo estudo preservará esse
resultado como evidência anterior e investigará o histórico temporal. Ele não reescreverá nem substituirá o protocolo
anterior.

## 2. Bloqueios anteriores ao protocolo

### G0 — viabilidade dos dados

As duas sequências com GT atuais, `1018-00` e `1018-13`, já foram abertas e analisadas. Elas podem ser usadas para
desenvolvimento, depuração e piloto, mas não formam um teste independente para hipóteses criadas depois de seus
resultados. `rellis_example` e `00000` continuam somente descritivas porque não têm GT validado.

Antes de continuar para um estudo confirmatório, é necessário:

1. inventariar sequências novas com GT, sem consultar erros das odometrias;
2. definir a sequência como unidade estatística independente;
3. fixar quantas sequências externas existirão e qual inferência é possível com esse número;
4. decidir a generalização alegada: outro percurso, outro ambiente, outro conjunto de sensores ou robô real.

Um teste exato de sinais ilustra o limite: com hipótese direcional unilateral e α = 0,05, `k = 5` só rejeita a hipótese
nula se as cinco sequências forem favoráveis (`p = 1/2⁵ = 0,03125`); no teste bilateral são necessárias pelo menos seis
sequências para que unanimidade alcance 5%. Isso é apenas um mínimo matemático, não uma justificativa geral de poder.
O número final deverá ser sustentado pela regra de decisão e pelo efeito mínimo relevante.

Se não houver sequências externas suficientes, o estudo será rotulado como **benchmark piloto/exploratório**, sem
alegação confirmatória nova.

O inventário catalográfico de 29/10/2026 encontrou oito candidatas públicas novas com VLIO e GT anunciado. Nenhum bag
externo foi aberto: a elegibilidade e o `k` final continuam pendentes da triagem estrutural cega. Com esse conjunto, a
alegação máxima será generalização para outro percurso no mesmo domínio e na mesma plataforma, não para outro ambiente
ou conjunto de sensores. Critérios, lista e barreira cega estão em `docs/INVENTORY_G0.md`.

### G1 — processamento cego do teste

O pipeline atual não mantém uma sequência nova cega:

- `scripts/run_sequence.sh` sempre chama `ofd.evaluate`;
- `ofd.extract` lê o tópico de GT embutido mesmo sem `--gt-bag` ou `--gt-tum`;
- `ofd.build_dataset` calcula `gt_*` e erros por método;
- `ofd.evaluate` atualiza `data/output/metrics.csv` e imprime ATE/RPE.

Portanto, nenhuma sequência candidata a teste poderá ser processada pelo comando atual. Antes disso deverá existir um
modo cego, coberto por testes, com o seguinte fluxo:

1. **Triagem estrutural:** verificar apenas presença, timestamps e duração de câmera, LiDAR, IMU e GT segundo critérios
   definidos antes da triagem. O processo expõe somente aprovação/reprovação, não distribuições, erros ou métricas. Usar
   todas as sequências elegíveis ou uma regra de seleção pré-fixada.
2. **Congelamento anterior ao teste:** registrar protocolo, commit, ambiente, modelos treinados e configurações antes
   de processar ou inspecionar as features das sequências externas.
3. **Extração sem GT:** ignorar explicitamente o tópico de GT, inclusive quando estiver dentro do bag, e gravar
   `gt.tum` vazio ou manter o GT em área inacessível ao processo de desenvolvimento.
4. **Tabela e predição cegas:** um job não interativo gera features e predições com os artefatos congelados; `gt_*` e
   `*_err_*` permanecem vazios, `ofd.evaluate` não roda e nenhuma estatística das features orienta decisões.
5. **Manifesto cego:** registrar hashes da tabela de features, runs, código, configurações, protocolo, modelos e
   predições antes de acessar o GT.
6. **Abertura única:** uma rotina separada verifica os hashes, anexa o GT sem alterar features, calcula métricas e gera
   o relatório final em uma execução auditável.
7. **Sem retorno ao desenvolvimento:** qualquer falha após a abertura é registrada e tratada conforme regra definida no
   protocolo; o resultado não pode orientar mudanças e nova tentativa informal.

Quando possível, uma pessoa que não escolhe modelos deverá custodiar o GT ou executar a abertura. Testes automatizados
deverão provar que o modo cego não grava métricas, alvos nem erros e que a anexação do GT não muda nenhum byte lógico das
features congeladas.

### G2 — baseline temporal sem aprendizado

Uma rede temporal pode parecer melhor apenas porque suaviza velocidades ruidosas. Ao mesmo tempo, uma cabeça W que
combina apenas twists atuais não deve ser comparada de forma primária com um filtro que pode suavizar se ela própria não
receber a mesma possibilidade. O núcleo adotará uma pós-filtragem comum:

- **Pα — EMA comum:** a mesma EMA causal, com o mesmo `α`, será aplicada às saídas de B5, F1-R/MLP-W, MLP-W com janela e
  CNN/LSTM-W. O valor será escolhido uma vez para favorecer B5 no piloto de desenvolvimento e congelado antes das
  grades neurais;
- **T1 — B5 + Pα:** média das fontes válidas seguida da EMA comum;
- **T2 — Kalman de twist:** estado de seis velocidades com dinâmica de persistência, atualização pelas fontes válidas,
  covariâncias estimadas apenas no treino e hiperparâmetros escolhidos na validação interna.

Assim, H1 compara **ponderação + a mesma suavização** contra **média + a mesma suavização**. As saídas sem Pα também
serão reportadas, mas não decidirão H1/H2. T2 permanece como comparador clássico forte; uma alegação confirmatória de
superioridade sobre ele só será adicionada como H3 se a análise de viabilidade mostrar poder suficiente. Equações,
inicialização e grades de Pα/T2 serão fechadas no protocolo.

Escolher `α` pela B5 é deliberadamente conservador: otimiza a pós-filtragem do comparador e pode ser subótimo para os
modelos aprendidos. Nenhum `α` específico por modelo será permitido e o valor não poderá ser reotimizado depois de ver
F1-R, MLP, CNN ou LSTM.

### G3 — hipótese e regra primárias

Não será permitido escolher um vencedor depois de olhar o teste. A seleção entre CNN e LSTM ocorrerá somente na
validação interna e será tratada como parte do pipeline do modelo principal.

Hipóteses hierárquicas candidatas:

- **H1:** o encoder temporal causal selecionado, com cabeça W e Pα, supera F1-R + Pα e B5 + Pα em RMSE linear e angular
  por uma margem prática pré-fixada, sem degradar RPE além da margem permitida.
- **H2, testada somente se H1 passar:** o mesmo modelo supera MLP-W + Pα com a mesma janela `W`. Isso separa o efeito da
  arquitetura do simples acesso ao contexto.
- **H3, opcional e testada somente se H2 passar:** o mesmo sistema supera T2/Kalman. H3 só entrará no protocolo se a
  análise de viabilidade sustentar essa terceira exigência; caso contrário, T2 será comparação descritiva.

Margens, número mínimo de sequências favoráveis, uso das sementes e regra de não inferioridade do RPE são
**A DEFINIR ANTES DO PROTOCOLO**. Todo resultado fora da hierarquia congelada será explicitamente exploratório.

## 3. Matriz mínima de modelos

| Papel | Modelos | Status |
|---|---|---|
| Fontes | B1–B4 e B5 | descritivo |
| Não temporal aprendido | B6 ridge | comparador secundário |
| Por passo | F1-R (MLP-W por passo) + Pα | comparador de H1, retreinado |
| Temporal clássico | T1 B5 + Pα e T2 Kalman | T1 em H1; T2 descritivo ou H3 |
| Mesmo contexto | MLP-W com janela + Pα | controle de H2 |
| Candidatos | CNN 1D-W + Pα e LSTM-W + Pα | um selecionado na validação interna |
| Saída direta | cabeça D no candidato selecionado | exploratório |
| Offline | BiLSTM e, se implementado, suavizador RTS | apêndice, fora da disputa online |
| Fontes removidas | leave-one-source-out no candidato | exploratório |
| Perda inesperada | um cenário FAST-LIO2 pré-fixado | exploratório |

### 3.1 F1 histórico e F1-R

Os resultados de F1 do primeiro experimento serão preservados apenas como registro histórico. Eles não serão reutilizados
em H1, pois foram ajustados em outra divisão e com outra regra de treinamento.

O novo comparador **F1-R** será uma MLP-W por passo retreinada do zero no mesmo LOSO, com a mesma normalização, sementes,
grade, orçamento de atualizações e critério de seleção das novas famílias. Depois receberá o mesmo Pα. F1-R não recebe
uma sequência explícita, mas suas 56 entradas incluem a variância causal `*_var_H` de um indicador com `H = 10`; o nome
correto é **MLP por passo com histórico resumido implícito H = 10**, e não “modelo sem histórico”. A MLP com janela
receberá os mesmos passos completos fornecidos à CNN/LSTM.

### 3.2 Cabeça de ponderação W

Em todos os modelos W:

- o encoder pode usar features históricas para calcular quatro pesos no instante `k`;
- os pesos de fontes inválidas em `k` são zero e os demais somam 1;
- a predição combina **somente os quatro twists atuais válidos em `k`**;
- twists passados não entram diretamente na combinação, evitando confundir ponderação com suavização aprendida.

T1 isola o efeito da mesma suavização aplicada à média; T2 representa uma fusão/filtragem clássica completa.

### 3.3 Pós-filtragem comum Pα

Pα não participa do gradiente nem da perda de treino. Cada rede será treinada sobre sua saída física sem pós-filtragem.
Na validação e na inferência, Pα recebe a predição depois da política de retenção causal e aplica
`y'_k = α y_k + (1 − α) y'_{k−1}` componente a componente. O mesmo `α`, a mesma inicialização e a mesma regra para
lacunas serão usados em B5, F1-R, MLP-W, CNN-W e LSTM-W. O valor de `α` será fixado com B5 nas duas dobras de
desenvolvimento e não será reotimizado por modelo.

A grade será restrita a `0 < α ≤ 1`; `α = 0` seria memória infinita e não será candidato.

Antes da primeira predição válida, a saída permanece zero. Na primeira predição válida da sequência, o estado será
inicializado diretamente com `y'_k = y_k`, sem mistura com zero; a EMA começa na predição válida seguinte. O filtro não
será reiniciado em lacunas de GT ou de fontes, apenas no início de uma nova sequência.

Configurações, CNN versus LSTM e o melhor orçamento de atualizações serão escolhidos pela perda padronizada calculada
**depois de Pα**. Para cada avaliação, o filtro percorre causalmente a sequência completa com a inicialização definida
acima e a perda é recortada apenas nos endpoints elegíveis; não há reset artificial no início de um bloco com GT. A
influência do estado anterior ao bloco interno será limitada pelo embargo de memória definido na seção 4.3.

Esse controle impede que um candidato vença apenas por receber uma suavização mais forte. T2 não usa Pα, pois é um
sistema clássico de fusão/filtragem próprio e será identificado separadamente.

### 3.4 Janela e regime da LSTM

Para a comparação principal, MLP-W, CNN-W e LSTM-W usarão a mesma janela causal de `W` passos. A LSTM será treinada e
executada com janela fixa e estado reiniciado entre exemplos, nunca em janelas no treino e sequência inteira no teste.
Estados também serão reiniciados no início de cada sequência.

`W` não fará parte das 18 configurações de cada família. Um único valor será escolhido no piloto pelo LOSO da MLP-W,
a partir de candidatos pré-declarados e com desempate em favor da menor janela. Isso ocorrerá antes das grades de
CNN/LSTM; o valor será então imposto à MLP-W, CNN-W e LSTM-W. Assim, H2 compara arquiteturas com exatamente o mesmo
contexto.

Dentro da janela:

- linhas sem GT podem entrar como features; o alvo é exigido apenas no passo final supervisionado;
- método inválido recebe `valid = 0` e todas as demais features desse método zeradas após a normalização;
- lacunas não são removidas nem aproximadas por outra fonte;
- a janela nunca atravessa a fronteira entre sequências.

### 3.5 BiLSTM

A BiLSTM padrão usa futuro e permanecerá somente como referência offline. Ela não poderá ser declarada vencedora do
sistema de navegação. Para reduzir o núcleo do artigo, sua execução pode ir ao apêndice; um suavizador RTS clássico é
uma referência offline alternativa.

## 4. Dados, divisão e campo receptivo

### 4.1 Desenvolvimento e teste

- **Desenvolvimento:** `1018-00` e `1018-13`, usadas para implementação, piloto e seleção interna sem alegação nova.
- **Teste externo:** `k` sequências novas elegíveis, mantidas no fluxo cego de G1.
- **RELLIS-3D:** inferência descritiva, sem métricas de erro.

Nenhuma linha será embaralhada aleatoriamente entre treino e validação/teste. A unidade externa é a sequência. O modelo
final será ajustado nos dados de desenvolvimento somente depois de arquitetura, janela e grades estarem congeladas.

### 4.2 Validação interna no desenvolvimento

A seleção principal imitará a generalização para outro percurso por **leave-one-sequence-out (LOSO)**:

1. dobra D-A: treinar em `1018-00` e validar em `1018-13`;
2. dobra D-B: treinar em `1018-13` e validar em `1018-00`;
3. agregar a perda das duas dobras e sementes pela regra pré-fixada.

A seleção será sequencial, toda dentro desse LOSO:

1. escolher `α` uma vez para B5 e congelar Pα;
2. escolher `W` com MLP-W entre candidatos pré-declarados e congelá-lo;
3. com `α` e `W` fixos, escolher configurações e CNN versus LSTM;
4. escolher hiperparâmetros de T2 sem usar nenhuma sequência externa.

Dentro da sequência de treino de cada dobra, blocos temporais com purga/embargo serão usados **somente para escolher o
orçamento de atualizações do otimizador** e detectar instabilidade. Eles não substituirão o LOSO como critério de
arquitetura/configuração. Normalização, covariâncias e qualquer estado ajustável serão recalculados apenas na sequência
de treino da dobra.

Com lote fixo de 64, cada checkpoint registrará o número cumulativo de chamadas a `optimizer.step()`. O melhor orçamento
de uma execução será o número de atualizações no mínimo da perda de validação **após Pα**. Para treinar o modelo da dobra
na sequência inteira, será usada a mediana, arredondada para cima, das atualizações selecionadas em todas as combinações
de bloco interno e semente daquela dobra.

Depois da seleção, o modelo externo final será treinado em `1018-00 + 1018-13` pelo número de atualizações derivado das
duas dobras de desenvolvimento: mediana, arredondada para cima, dos dois orçamentos de dobra da configuração selecionada.
Não será usado o mesmo número de épocas. Os lotes serão reembaralhados quando o iterador esgotar e o treino parará
exatamente no orçamento fixado, ainda que no meio de uma época. Serão reportados tanto atualizações quanto épocas
efetivas para cada tamanho de treino.

Transportar atualizações é uma **regra pré-fixada de orçamento**, não uma alegação de equivalência entre treinar em uma
ou duas sequências. O número ótimo de atualizações pode crescer com mais dados; essa limitação será declarada e não será
corrigida depois de observar o teste externo.

### 4.3 Campo receptivo e purga

Definições:

- `H = 10`: janela causal já usada na variância de indicadores;
- `W`: janela explícita do modelo temporal;
- `R = W + H − 1`: campo receptivo máximo em linhas brutas.
- `ε = 0,01`: peso residual máximo aceito para a memória anterior de Pα;
- `M_α = ⌈ln(ε) / ln(1 − α)⌉` para `0 < α < 1`, e `M_α = 0` para `α = 1`.

Nas subdobras temporais:

1. o embargo de alvo `E_gt` reduzirá dependência pela autocorrelação de `gt_*`; sua fórmula, limiar e limite máximo
   serão definidos usando apenas treino e congelados no protocolo;
2. antes do bloco, serão excluídas do treino pelo menos `E_antes = max(E_gt, R + M_α)` linhas. O termo `R` protege o
   campo receptivo e `M_α` reduz a contribuição do estado formado por predições in-sample a no máximo `ε`;
3. depois do bloco, serão excluídas do treino pelo menos `E_depois = max(E_gt, R)` linhas. Pα é causal, portanto não
   exige termo de memória no lado posterior;
4. a validação poderá usar como contexto as features do embargo anterior, que não participam do ajuste do modelo e
   nunca incluem o alvo como entrada;
5. linhas sem GT dentro do contexto são permitidas, mas somente endpoints com as seis componentes do alvo finitas
   contribuem para perda e métricas.

A implementação usará máscaras distintas para endpoints supervisionados, contexto e linhas embargadas. Um teste de
índices verificará a fórmula com casos de fronteira, sem depender apenas de inspeção visual. Valores candidatos de `α`
que tornem uma subdobra estruturalmente inviável serão rejeitados por regra anterior às métricas, não depois de observar
seu desempenho. O protocolo fixará, antes das grades, um `α_min` e uma fração máxima da subdobra que pode ser consumida
pelos embargos; ambos serão critérios estruturais independentes da perda.

### 4.4 Testes de causalidade

- alterar todas as linhas futuras e confirmar que predições anteriores da CNN/LSTM causal não mudam;
- confirmar que nenhuma janela atravessa sequências;
- confirmar que janelas de treino posteriores não alcançam o bloco de validação após a purga;
- substituir por valores limitados as predições anteriores ao início do embargo `E_antes` e confirmar que a diferença
  no estado de Pα na primeira linha avaliada não excede `ε` vezes a diferença inicial, além da tolerância numérica
  pré-fixada;
- confirmar que contexto sem GT não introduz alvo ou coluna de avaliação nas features;
- confirmar que o modo cego de G1 não materializa qualquer métrica derivada do GT.

## 5. Comparação justa e seleção

Todos os modelos causais compartilharão:

- as mesmas 56 features por passo, máscaras, alvos e divisões;
- normalização e imputação ajustadas somente no treino;
- a mesma perda de treino sem Pα e a mesma perda de seleção após Pα;
- o mesmo conjunto de sementes e a mesma regra para orçamento de atualizações;
- **18 configurações por família neural**, como na grade atual, salvo emenda anterior ao protocolo;
- o mesmo `W` e o mesmo Pα, ambos fixados antes das grades neurais;
- faixas numéricas pré-declaradas de parâmetros, regularização e atualizações máximas;
- um teto de parâmetros definido antes de abrir o teste externo;
- o mesmo hardware, tamanho de lote e procedimento de medição para eficiência.

O número idêntico de configurações reduz vantagem de busca, mas não garante custo igual; número de treinamentos, tempo e
energia serão reportados. Baselines clássicos terão grades próprias pré-fixadas, sem inflá-las artificialmente até 18.

F1-R, MLP-W, CNN-W e LSTM-W serão treinados sem Pα; suas configurações e a escolha CNN versus LSTM usarão a perda LOSO
após Pα nas duas dobras de desenvolvimento. Empates favorecerão o modelo menor e, persistindo, o de menor latência. A
sequência externa não participará da escolha.

Pα será escolhido uma vez com B5 no LOSO e então aplicado sem reotimização a todos os modelos W. Configurações de T2
também serão decididas somente pelo LOSO. T1 e T2 serão reportados no teste, mas nenhum poderá ser promovido olhando
métricas externas.

Como as janelas sobrepostas não são observações independentes e o conjunto atual tem poucos minutos contínuos, o teto
de parâmetros e o valor de `W` deverão ser conservadores. Eles podem ser estudados no piloto já visto, mas serão
congelados antes das grades finais e da aquisição de qualquer resultado externo.

## 6. Fontes, ablação e perda inesperada

### 6.1 Núcleo

Todos os comparadores de H1/H2 usarão as quatro fontes. As diferenças de cobertura continuarão visíveis por máscaras;
nenhuma linha será descartada apenas porque uma fonte está ausente.

### 6.2 Ablação com retreino

Somente o candidato selecionado será retreinado nas quatro condições leave-one-source-out. Para cada condição serão
reportados:

- métricas globais, usando retenção causal da última predição quando nenhuma fonte estiver válida e zero antes da
  primeira predição válida, como no protocolo anterior;
- cobertura conjunta do conjunto de fontes restante;
- métricas condicionadas às linhas em que ao menos uma fonte do conjunto está válida;
- contagem de linhas e duração, para impedir comparação de suportes diferentes sem aviso.

Condições “somente visual” ou “somente família LiDAR” saem do núcleo e só serão adicionadas por emenda anterior ao
protocolo.

### 6.3 Perda de fonte sem retreino

O cenário mínimo será a perda do FAST-LIO2, por corresponder à cobertura limitada da IMU observada. Instantes, duração e
frequência serão fixados sem olhar o erro. Ao mascarar a fonte:

- `fastlio_valid = 0`;
- todas as demais features FAST-LIO2 serão zeradas depois da normalização;
- os twists FAST-LIO2 não poderão entrar na cabeça W;
- o cenário será reconhecido como potencialmente fora da distribuição de treino.

O uso de aumento por remoção aleatória de fontes durante o treino será decidido antes do protocolo. Se houver comparação
com e sem aumento, ela será exploratória ou terá correção própria; não poderá ser escolhida pelo teste.

## 7. Métricas e regra de decisão

### 7.1 Primárias

- RMSE vetorial da velocidade linear por sequência, em m/s;
- RMSE vetorial da velocidade angular por sequência, em rad/s.

Para cada modelo e sequência, sementes serão combinadas por média de métricas ou ensemble de predições; uma única opção
será fixada no protocolo. O desvio entre sementes será reportado, mas não será usado como limiar de relevância.

### 7.2 Guarda de trajetória

Como o primeiro F2 obteve RMSE competitivo e deriva elevada, H1 incluirá uma guarda de não inferioridade no RPE de
10 m. A margem máxima de piora será fixada antes do teste. ATE continuará secundária, pois depende do trecho e do
alinhamento global, mas qualquer deriva grande será destacada.

### 7.3 Regra candidata

H1 somente será positiva se o candidato W + Pα satisfizer, contra **F1-R + Pα** e contra **T1/B5 + Pα**:

1. a melhora relativa mediana por sequência for pelo menos `δ_v` em RMSE linear e `δ_ω` em RMSE angular;
2. a quantidade de sequências que excede cada margem satisfizer a regra exata pré-fixada para `k`;
3. o RPE de 10 m não piorar mais que `δ_RPE`;
4. todas as métricas estiverem definidas no número mínimo de sequências estabelecido.

H2 será testada somente após H1 e aplicará a mesma lógica contra **MLP-W + Pα com o mesmo `W`**. H3 contra T2/Kalman
só será confirmatória se estiver no protocolo antes da abertura; caso contrário será descritiva. A ordem hierárquica
evita uma correção adicional entre hipóteses testadas apenas após a anterior passar. Valores de `δ_v`, `δ_ω`,
`δ_RPE`, `k` e a direção do teste ainda dependem da decisão de relevância prática e serão fixados antes da abertura.

### 7.4 Gate de viabilidade estatística

Antes do pré-registro, o piloto LOSO produzirá as diferenças relativas por dobra para todas as condições de H1/H2. Ele
não fornecerá uma estimativa confiável de poder com apenas duas sequências, mas servirá para detectar contradições
óbvias — por exemplo, melhora angular acompanhada de piora linear nas duas dobras.

Com `δ_v`, `δ_ω`, `δ_RPE` e a regra por sequência definidos por relevância prática, será feita uma análise de
sensibilidade para o `k` disponível: probabilidade de satisfazer toda a conjunção sob uma faixa explícita de taxas de
sucesso e tamanhos de efeito. O limiar de viabilidade será acordado com o orientador antes do protocolo. As margens não
serão reduzidas para tornar o teste aprovável.

Se a regra tiver chance desprezível de passar ou `k` não permitir a inferência escolhida, o estudo será simplificado ou
rotulado exploratório **antes** de qualquer abertura externa.

### 7.5 Secundárias e exploratórias

- RMSE das seis componentes;
- RPE, ATE e velocidade integrada;
- saídas de B5/F1-R/MLP/CNN/LSTM antes de Pα, para separar ponderação e pós-filtragem;
- primárias por quantidade e identidade das fontes válidas;
- erro antes, durante e depois da perda de uma fonte e tempo de recuperação;
- pesos da cabeça W e sua estabilidade;
- cobertura global e condicional das ablações;
- dispersão entre sementes;
- latência, frequência, memória e parâmetros.

Scans sucessivos não serão tratados como amostras independentes. A significância por linha não substituirá consistência
por sequência.

## 8. Variabilidade das odometrias visuais

O dataset atual contém uma realização oficial de cada VO, embora sua variabilidade entre execuções já esteja
documentada. Um modelo temporal pode aprender padrões específicos dessa realização.

O teste principal usará uma única realização oficial: nas sequências existentes, a realização do dataset v1; nas novas,
a primeira execução completa do pipeline congelado que satisfizer critérios operacionais definidos sem GT. Uma nova
tentativa só poderá ocorrer por falha operacional prevista no protocolo, nunca pelo erro da trajetória.

Repetições de ORB-SLAM3 e Stella, se executadas em número pré-fixado e ainda no fluxo cego, entrarão apenas como análise
de sensibilidade. Nenhuma repetição poderá substituir a realização principal ou ser escolhida pelo GT externo.

## 9. Plano de implementação

### Fase 0 — resolver G0–G3

- inventariar dados externos e fechar o status confirmatório ou exploratório;
- implementar e validar o modo cego;
- fechar Pα, T2, hipótese, regra e matriz mínima;
- definir hardware-alvo ou retirar eficiência como pergunta de pesquisa.

### Fase 1 — infraestrutura sem teste externo

- criar janelas, máscaras de endpoint/contexto e purga/embargo;
- separar encoder da cabeça W/D;
- implementar Pα, T1, T2, F1-R, MLP-W com janela, CNN-W, LSTM-W e referências exploratórias;
- preservar os resultados históricos de F1/F2 sem reutilizar seus modelos em H1;
- gravar configuração, semente, commit e hashes em cada artefato.

### Fase 2 — testes sintéticos e de contrato

- causalidade, fronteira de sequência, purga e ausência de vazamento;
- máscara completa de fonte inválida;
- tarefa em que o alvo depende de histórico conhecido;
- tarefa em que o alvo é constante ou suave, verificando se o ganho vem apenas de filtragem;
- comparação de T1/T2 e modelos aprendidos sob ruído controlado;
- teste de que Pα usa exatamente os mesmos parâmetros e ordem de operações em todas as saídas W;
- determinismo por semente e registro de falhas;
- modo cego e abertura com preservação das features.

### Fase 3 — piloto nos dados já vistos

- fixar `W` e `α` antes das grades neurais;
- executar o LOSO de desenvolvimento e fechar faixas de capacidade;
- estimar custo, estabilidade e a viabilidade da conjunção H1/H2 para o `k` disponível;
- identificar defeitos de implementação;
- não apresentar o piloto como confirmação;
- congelar código e decisões antes de qualquer resultado externo.

### Fase 4 — revisão e pré-registro

- revisar o plano com orientador e revisor externo;
- somente prosseguir como confirmatório se G0 e o gate de viabilidade forem satisfeitos;
- escrever novo `docs/protocol_*.md` com todos os números ainda pendentes;
- registrar protocolo, commit, ambiente, modelos e manifesto antes da abertura.

### Fase 5 — execução bloqueada

- ajustar somente no desenvolvimento;
- produzir predições e hashes no teste cego;
- auditar artefatos;
- abrir o GT uma vez e registrar resultado positivo, negativo ou inconclusivo sem alterar a regra.

## 10. Artefatos previstos

```text
data/analysis/model_comparison/
  blind/feature_manifest.json
  blind/prediction_manifest.json
  phase1/<fold>/<model>/cv.csv
  phase1/<fold>/<model>/selected.json
  phase2/test_metrics.csv
  phase2/source_ablations.csv
  phase2/source_dropout.csv
  phase2/efficiency.csv
  phase2/predictions/
  unlock_manifest.json
  decision.json
```

O estudo não sobrescreverá `data/analysis/fusion/`. Serão mantidos plano, parecer, resposta ao parecer, protocolo,
relatórios operacionais, resultados e manifestos.

## 11. Narrativa possível do artigo

Condicionada à aprovação de G0–G3:

1. benchmark de quatro fontes com propriedades complementares;
2. comparação controlada entre ponderação por passo, filtragem clássica e fusão temporal aprendida;
3. controle de janela que separa contexto de arquitetura;
4. ablação de contribuição e um cenário realista de perda de fonte;
5. processamento cego e avaliação por sequência.

Título de trabalho:

> **Learned Temporal Fusion versus Classical Smoothing for Heterogeneous Odometry Sources**

BiLSTM, cabeça direta e eficiência sem hardware-alvo não sustentarão a alegação principal. O resultado negativo do
primeiro experimento permanecerá visível e nenhuma conclusão será generalizada para ambientes ou sensores não testados.

## 12. Decisões para a próxima reunião

1. Quantas sequências com GT ainda não analisadas existem e quais passam critérios estruturais pré-fixados?
2. Quem pode custodiar o GT ou executar a abertura única?
3. O artigo será confirmatório ou um benchmark piloto se `k` for pequeno?
4. Qual formulação e grade serão usadas em T2/Kalman?
5. Quais margens `δ_v`, `δ_ω` e `δ_RPE` representam melhora prática e qual chance mínima torna H1 viável?
6. H3 contra Kalman terá poder para ser confirmatória ou ficará descritiva?
7. Quantas repetições de VO cabem na análise de sensibilidade?
8. Haverá aumento por remoção de fontes no treino?
9. Existe hardware-alvo? Sem ele, eficiência será apenas uma tabela descritiva.
