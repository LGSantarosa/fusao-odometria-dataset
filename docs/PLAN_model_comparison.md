# Plano de estudo — comparação de arquiteturas para fusão de odometrias

> **RASCUNHO REVISADO — 29/10/2026.** Documento atualizado após revisão externa e verificação do pipeline. Ainda não
> é um protocolo pré-registrado, não autoriza abrir novas sequências de teste e não altera o experimento concluído em
> `docs/protocol_fusion_model.md`. A triagem do parecer está em
> `docs/REVIEW_RESPONSE_model_comparison_2026-10-29.md`. Os bloqueios G0–G3 abaixo precisam ser resolvidos antes do
> novo protocolo.

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

Uma rede temporal pode parecer melhor apenas porque suaviza velocidades ruidosas. O núcleo do estudo incluirá pelo
menos um filtro temporal causal clássico, além da MLP por passo:

- **T1 — EMA-B5:** média exponencial causal aplicada à média das fontes válidas, com `α` escolhido somente na validação
  interna e retenção quando nenhuma fonte estiver válida;
- **T2 — Kalman de twist:** estado de seis velocidades com dinâmica de persistência, atualização pelas fontes válidas,
  covariâncias estimadas apenas no treino e hiperparâmetros escolhidos na validação interna.

T1 é o controle mínimo contra simples filtragem passa-baixa. T2 é o comparador clássico esperado em robótica. Equações,
regularização das covariâncias, grades e inicialização deverão ser fechadas no protocolo. Se T2 for retirado por motivo
técnico, a justificativa deverá ser registrada antes do teste.

### G3 — hipótese e regra primárias

Não será permitido escolher um vencedor depois de olhar o teste. A seleção entre CNN e LSTM ocorrerá somente na
validação interna e será tratada como parte do pipeline do modelo principal.

Hipóteses hierárquicas candidatas:

- **H1:** o encoder temporal causal selecionado, com cabeça de ponderação W, supera F1 e o melhor baseline temporal
  clássico em RMSE linear e angular por uma margem prática pré-fixada, sem degradar RPE além da margem permitida.
- **H2, testada somente se H1 passar:** o mesmo modelo supera a MLP-W que recebe a mesma janela. Isso separa o efeito
  da arquitetura do simples acesso ao contexto.

Margens, número mínimo de sequências favoráveis, uso das sementes e regra de não inferioridade do RPE são
**A DEFINIR ANTES DO PROTOCOLO**. Todo resultado fora de H1/H2 será explicitamente exploratório.

## 3. Matriz mínima de modelos

| Papel | Modelos | Status |
|---|---|---|
| Fontes | B1–B4 e B5 | descritivo |
| Não temporal aprendido | B6 ridge | comparador secundário |
| Por passo | F1/MLP-W | comparador de H1 |
| Temporal clássico | T1 EMA-B5 e T2 Kalman | comparadores de H1 |
| Mesmo contexto | MLP-W com janela | controle de H2 |
| Candidatos | CNN 1D-W causal e LSTM-W | um selecionado na validação interna |
| Saída direta | cabeça D no candidato selecionado | exploratório |
| Offline | BiLSTM e, se implementado, suavizador RTS | apêndice, fora da disputa online |
| Fontes removidas | leave-one-source-out no candidato | exploratório |
| Perda inesperada | um cenário FAST-LIO2 pré-fixado | exploratório |

### 3.1 O que “por passo” significa

F1 não recebe uma sequência explícita, mas suas 56 entradas já incluem a variância causal `*_var_H` de um indicador
com `H = 10`. O nome correto no novo estudo será **MLP por passo com histórico resumido implícito H = 10**, e não
“modelo sem histórico”. A MLP com janela receberá os mesmos passos completos fornecidos à CNN/LSTM.

### 3.2 Cabeça de ponderação W

Em todos os modelos W:

- o encoder pode usar features históricas para calcular quatro pesos no instante `k`;
- os pesos de fontes inválidas em `k` são zero e os demais somam 1;
- a predição combina **somente os quatro twists atuais válidos em `k`**;
- twists passados não entram diretamente na combinação, evitando confundir ponderação com suavização aprendida.

O baseline T1/T2 mede separadamente o ganho obtido apenas por filtragem temporal.

### 3.3 Janela e regime da LSTM

Para a comparação principal, MLP-W, CNN-W e LSTM-W usarão a mesma janela causal de `W` passos. A LSTM será treinada e
executada com janela fixa e estado reiniciado entre exemplos, nunca em janelas no treino e sequência inteira no teste.
Estados também serão reiniciados no início de cada sequência.

Dentro da janela:

- linhas sem GT podem entrar como features; o alvo é exigido apenas no passo final supervisionado;
- método inválido recebe `valid = 0` e todas as demais features desse método zeradas após a normalização;
- lacunas não são removidas nem aproximadas por outra fonte;
- a janela nunca atravessa a fronteira entre sequências.

### 3.4 BiLSTM

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

### 4.2 Campo receptivo e purga

Definições:

- `H = 10`: janela causal já usada na variância de indicadores;
- `W`: janela explícita do modelo temporal;
- `R = W + H − 1`: campo receptivo máximo em linhas brutas.

Nas subdobras temporais:

1. janelas de treino posteriores ao bloco de validação terão purga de pelo menos `R` linhas, impedindo que contenham
   features do bloco de validação;
2. um embargo de alvo será aplicado nas bordas para reduzir dependência pela autocorrelação de `gt_*`; sua fórmula,
   limiar, limite máximo e direção serão definidos usando apenas treino e congelados no protocolo;
3. a validação poderá usar, como contexto, features anteriores ao início do bloco, pois são entradas disponíveis
   causalmente e nunca incluem o alvo; essa escolha será registrada explicitamente;
4. linhas sem GT dentro do contexto são permitidas, mas somente endpoints com as seis componentes do alvo finitas
   contribuem para perda e métricas.

A implementação usará máscaras distintas para endpoints supervisionados, contexto e linhas embargadas. Um teste de
índices verificará a fórmula com casos de fronteira, sem depender apenas de inspeção visual.

### 4.3 Testes de causalidade

- alterar todas as linhas futuras e confirmar que predições anteriores da CNN/LSTM causal não mudam;
- confirmar que nenhuma janela atravessa sequências;
- confirmar que janelas de treino posteriores não alcançam o bloco de validação após a purga;
- confirmar que contexto sem GT não introduz alvo ou coluna de avaliação nas features;
- confirmar que o modo cego de G1 não materializa qualquer métrica derivada do GT.

## 5. Comparação justa e seleção

Todos os modelos causais compartilharão:

- as mesmas 56 features por passo, máscaras, alvos e divisões;
- normalização e imputação ajustadas somente no treino;
- perda principal matematicamente equivalente;
- o mesmo conjunto de sementes e a mesma regra para número de épocas;
- **18 configurações por família neural**, como na grade atual, salvo emenda anterior ao protocolo;
- faixas numéricas pré-declaradas de `W`, parâmetros, regularização e épocas;
- um teto de parâmetros definido antes de abrir o teste externo;
- o mesmo hardware, tamanho de lote e procedimento de medição para eficiência.

O número idêntico de configurações reduz vantagem de busca, mas não garante custo igual; número de treinamentos, tempo e
energia serão reportados. Baselines clássicos terão grades próprias pré-fixadas, sem inflá-las artificialmente até 18.

CNN ou LSTM será escolhida pela perda média de validação interna conforme regra pré-registrada. Empates favorecerão o
modelo menor e, persistindo, o de menor latência. A sequência externa não participará da escolha.

Da mesma forma, configurações de T1/T2 e a regra que define o comparador clássico principal serão decididas somente na
validação interna. T1 e T2 serão reportados no teste, mas nenhum deles poderá ser promovido olhando suas métricas
externas.

Como as janelas sobrepostas não são observações independentes e o conjunto atual tem poucos minutos contínuos, o teto
de parâmetros e a grade de janelas deverão ser conservadores. Seus valores podem ser estudados no piloto já visto, mas
serão congelados antes da aquisição de qualquer resultado externo.

## 6. Fontes, ablação e perda inesperada

### 6.1 Núcleo

Todos os comparadores de H1/H2 usarão as quatro fontes. As diferenças de cobertura continuarão visíveis por máscaras;
nenhuma linha será descartada apenas porque uma fonte está ausente.

### 6.2 Ablação com retreino

Somente o candidato selecionado será retreinado nas quatro condições leave-one-source-out. Para cada condição serão
reportados:

- métricas globais, com a política pré-definida para linha sem nenhuma fonte;
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

H1 somente será positiva se, para F1 e para o melhor baseline temporal clássico:

1. a melhora relativa mediana por sequência for pelo menos `δ_v` em RMSE linear e `δ_ω` em RMSE angular;
2. a quantidade de sequências que excede cada margem satisfizer a regra exata pré-fixada para `k`;
3. o RPE de 10 m não piorar mais que `δ_RPE`;
4. todas as métricas estiverem definidas no número mínimo de sequências estabelecido.

H2 será testada somente após H1 e aplicará a mesma lógica contra a MLP-W de janela. Essa ordem hierárquica evita uma
correção adicional entre H1 e H2. Valores de `δ_v`, `δ_ω`, `δ_RPE`, `k` e a direção do teste ainda dependem da decisão
de relevância prática e serão fixados antes da abertura.

### 7.4 Secundárias e exploratórias

- RMSE das seis componentes;
- RPE, ATE e velocidade integrada;
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

Antes do protocolo deverá ser escolhida uma destas opções:

1. repetir ORB-SLAM3 e Stella nas sequências de desenvolvimento e teste segundo número/semente pré-fixados, agregando a
   sensibilidade sem selecionar a melhor execução; ou
2. manter uma execução oficial definida por regra operacional anterior ao GT e declarar explicitamente que a
   generalização entre realizações não foi medida.

Nenhuma execução poderá ser escolhida pelo erro contra o GT externo.

## 9. Plano de implementação

### Fase 0 — resolver G0–G3

- inventariar dados externos e fechar o status confirmatório ou exploratório;
- implementar e validar o modo cego;
- fechar baseline temporal, hipótese, regra e matriz mínima;
- definir hardware-alvo ou retirar eficiência como pergunta de pesquisa.

### Fase 1 — infraestrutura sem teste externo

- criar janelas, máscaras de endpoint/contexto e purga/embargo;
- separar encoder da cabeça W/D;
- implementar T1, T2, MLP-W com janela, CNN-W, LSTM-W e referências exploratórias;
- preservar F1/F2 atuais sem alterar seus resultados;
- gravar configuração, semente, commit e hashes em cada artefato.

### Fase 2 — testes sintéticos e de contrato

- causalidade, fronteira de sequência, purga e ausência de vazamento;
- máscara completa de fonte inválida;
- tarefa em que o alvo depende de histórico conhecido;
- tarefa em que o alvo é constante ou suave, verificando se o ganho vem apenas de filtragem;
- comparação de T1/T2 e modelos aprendidos sob ruído controlado;
- determinismo por semente e registro de falhas;
- modo cego e abertura com preservação das features.

### Fase 3 — piloto nos dados já vistos

- estimar custo e estabilidade e fechar faixas de janela/capacidade;
- identificar defeitos de implementação;
- não apresentar o piloto como confirmação;
- congelar código e decisões antes de qualquer resultado externo.

### Fase 4 — revisão e pré-registro

- revisar o plano com orientador e revisor externo;
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

> **Causal Temporal Fusion of Heterogeneous Odometry Sources beyond Classical Smoothing**

BiLSTM, cabeça direta e eficiência sem hardware-alvo não sustentarão a alegação principal. O resultado negativo do
primeiro experimento permanecerá visível e nenhuma conclusão será generalizada para ambientes ou sensores não testados.

## 12. Decisões para a próxima reunião

1. Quantas sequências com GT ainda não analisadas existem e quais passam critérios estruturais pré-fixados?
2. Quem pode custodiar o GT ou executar a abertura única?
3. O artigo será confirmatório ou um benchmark piloto se `k` for pequeno?
4. T2/Kalman entra obrigatoriamente no núcleo e qual formulação será usada?
5. Quais margens `δ_v`, `δ_ω` e `δ_RPE` representam melhora prática?
6. A VO será repetida ou sua realização única ficará como limitação explícita?
7. Haverá aumento por remoção de fontes no treino?
8. Existe hardware-alvo? Sem ele, eficiência será apenas uma tabela descritiva.
