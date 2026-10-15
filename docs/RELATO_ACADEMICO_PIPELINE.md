# Construção e validação do dataset derivado de odometrias visual e LiDAR

**Documento-base para os capítulos de Metodologia e Resultados**

**Data de consolidação:** 15 de outubro de 2026

**Estado:** experimentos de fumaça e sequências completas BotanicGarden 1018-13 (com GT) e RELLIS-3D 00000 (sem GT,
exploratória) processados.

Este documento registra, em linguagem acadêmica, as decisões metodológicas, os procedimentos experimentais e os
resultados obtidos durante a construção do dataset derivado que alimentará o modelo de fusão adaptativa. A organização
foi alinhada à qualificação de mestrado *Uma Abordagem de Fusão de Odometrias Visual e LiDAR para Navegação Robusta de
Robôs Móveis em Ambientes Dinâmicos*. Os registros operacionais, comandos e artefatos de auditoria permanecem nos demais
documentos do repositório e constituem a evidência reproduzível das afirmações apresentadas aqui.

## 1. Objetivo e relação com a pesquisa

O objetivo desta etapa é produzir uma base experimental comum para comparar fontes de odometria visual e baseada em
LiDAR e, posteriormente, treinar um modelo capaz de selecionar ou ponderar essas fontes conforme sua confiabilidade.
Para cada instante de referência, o dataset derivado reúne: (i) o incremento de pose estimado por cada método; (ii) o
intervalo temporal efetivamente coberto por esse incremento; (iii) indicadores de qualidade calculados causalmente; e
(iv) o incremento correspondente do *Ground Truth* (GT), empregado apenas como rótulo e na avaliação.

Esta etapa responde parcialmente à primeira questão de pesquisa da dissertação, pois estabelece como as odometrias
isoladas serão comparadas em ambientes não estruturados. Ela também cria a entrada necessária para responder à segunda
questão, referente à comparação entre odometrias individuais e a futura abordagem de seleção ou fusão adaptativa. O
modelo de aprendizado propriamente dito não integra o escopo deste repositório.

## 2. Metodologia

### 2.1 Delineamento experimental

Adotou-se experimentação computacional com dados públicos e sequências reais previamente gravadas. Todos os métodos
recebem, tanto quanto possível, os mesmos dados sensoriais e são avaliados sobre uma grade temporal comum definida pelo
fim de cada varredura LiDAR. O delineamento preserva a causalidade: uma estimativa só pode ser utilizada em um instante
se já estiver disponível nesse instante, sem interpolação com poses futuras.

O desenvolvimento foi dividido em três níveis de validação. Testes unitários verificam as operações geométricas, a
sincronização, o contrato da tabela e os indicadores. Um teste ponta a ponta sintético verifica a integração de todos os
estágios sem depender de grandes arquivos externos. Por fim, experimentos de fumaça com dados reais verificam a
compatibilidade das calibrações, dos formatos e dos executáveis antes da execução das sequências completas.

### 2.2 Seleção dos datasets

Foram selecionados os datasets BotanicGarden e RELLIS-3D. Essa seleção atualiza a proposta apresentada na qualificação,
que também considerava WildScenes e GOOSE. A alteração decorreu da necessidade de sequências contínuas que reunissem
imagens estéreo, nuvens de pontos, dados inerciais, calibração entre sensores e referência de trajetória compatível com
avaliação quadro a quadro. BotanicGarden e RELLIS-3D satisfazem esses requisitos de maneira mais direta para o objetivo
experimental desta etapa.

O BotanicGarden é o dataset principal. Ele foi capturado em um jardim botânico, contém ambientes naturais não
estruturados e fornece câmeras estéreo, LiDAR Velodyne VLP-16, unidades inerciais e uma trajetória de referência associada
a um levantamento realizado com scanner Leica RTC360 (LIU et al., 2024). A qualidade do GT é registrada como
`survey`. A precisão aproximada de 11 mm informada pelos autores refere-se ao mapa levantado e não deve ser interpretada
como garantia independente para cada pose da trajetória.

O RELLIS-3D é utilizado como dataset secundário por representar navegação *off-road* e disponibilizar câmera estéreo,
LiDAR Ouster OS1-64, IMU e odometria de rodas (JIANG et al., 2021). O arquivo `poses.txt` fornece uma pose por varredura
Ouster, porém sua origem metrológica não é declarada na documentação oficial. Por esse motivo, sua qualidade é registrada
como `slam`, e os resultados obtidos com esse GT devem ser interpretados considerando possível correlação com métodos
baseados em LiDAR.

### 2.3 Métodos de odometria

Quatro métodos foram escolhidos para representar fontes com propriedades distintas. ORB-SLAM3 e Stella VSLAM operam
com o par estéreo sem utilizar IMU e com fechamento de loop desativado. Essa configuração faz com que as poses registradas
representem odometria causal, sem correções futuras decorrentes de revisitas. KISS-ICP representa odometria LiDAR pura.
FAST-LIO representa odometria LiDAR-inercial fortemente acoplada.

| Método | Modalidade | Entrada principal | IMU | Configuração relevante |
|---|---|---|---:|---|
| ORB-SLAM3 | odometria visual | imagens estéreo | não | fechamento de loop desativado |
| Stella VSLAM | odometria visual | imagens estéreo | não | fechamento de loop desativado |
| KISS-ICP 1.3.0 | odometria LiDAR | nuvens de pontos | não | *deskew* decidido experimentalmente |
| FAST-LIO2 | odometria LiDAR-inercial | nuvens de pontos e IMU | sim | execução por ROS 2 e poses causais |

Fonte: Elaborada pelo autor (2026).

A presença da IMU no FAST-LIO impede tratá-lo como uma odometria LiDAR pura. Portanto, comparações entre FAST-LIO e os
demais métodos são apresentadas como comparação entre sistemas de odometria, não como ablação exclusiva da modalidade
sensorial. Essa diferença constitui uma ameaça ao construto e será explicitada na análise final.

### 2.4 Pipeline de processamento

O pipeline é composto por cinco estágios. Primeiro, o arquivo ROS bag é extraído em imagens estéreo, nuvens de pontos,
timestamps e calibração. Todos os campos originais relevantes da nuvem são preservados, incluindo intensidade, anel do
laser e tempo por ponto. Segundo, cada método é executado separadamente e produz poses causais, estado de rastreamento,
indicadores internos e metadados de versão. Terceiro, as poses são convertidas para um referencial corporal comum,
sincronizadas causalmente e transformadas em incrementos. Quarto, os resultados são reunidos em uma tabela com papéis
explícitos para metadados, atributos, rótulos e colunas exclusivas de avaliação. Quinto, são calculadas as métricas de
trajetória, cobertura e continuidade.

A pose segue a convenção \(T_{W,B}\), que transforma coordenadas do corpo \(B\) para o mundo \(W\). O incremento entre
dois instantes é definido por

\[
\Delta T_k = T_{W,B,k-1}^{-1} T_{W,B,k}.
\]

Assim, a componente de translação do incremento é expressa no referencial corporal do instante anterior. Estimativas
produzidas em outros sensores são convertidas para o referencial do LiDAR por conjugação com as extrínsecas fornecidas
pelo dataset. Os quatérnios são armazenados na ordem \((q_x,q_y,q_z,q_w)\), com sinal normalizado para \(q_w \ge 0\).

A grade temporal utiliza o final das varreduras LiDAR, pois uma estimativa baseada na varredura só se torna disponível
depois da captura do último ponto. Para cada método, seleciona-se a pose mais recente cujo timestamp não excede o instante
da grade. A pose é aceita apenas quando sua idade está dentro do limite configurado para o dataset. Não há interpolação
das odometrias. O GT, que não é entrada do modelo, pode ser interpolado para produzir o rótulo no mesmo intervalo temporal
do método avaliado.

Além do incremento rígido, a tabela armazena `dt`, que representa o intervalo efetivamente coberto, e `age`, que mede a
idade da estimativa no instante da grade. Também é calculada a velocidade incremental no grupo de Lie \(SE(3)\):

\[
\boldsymbol{v}_k = \frac{\log(\Delta T_k)}{\Delta t_k}.
\]

Essa representação permite comparar fontes assíncronas sem assumir que todos os incrementos cobrem o mesmo período. A
decisão entre utilizar \(\Delta T + \Delta t + age\) ou a velocidade em \(\mathfrak{se}(3)\) como entrada definitiva do
modelo permanece dependente da arquitetura de fusão.

### 2.5 Indicadores de qualidade

Para as odometrias visuais, são registrados o número de características, a quantidade de *inliers*, o erro médio de
reprojeção e a razão de pontos rastreados. Esses indicadores são coletados no momento do rastreamento, antes de qualquer
otimização global futura. Para KISS-ICP e FAST-LIO, são calculados uniformemente o *fitness* do registro, o RMSE dos
*inliers*, a razão de pontos sem correspondência e o número de pontos da varredura.

A razão de pontos sem correspondência substituiu a denominação inicial de “dinamicidade”. A mudança evita atribuir ao
indicador uma interpretação que os dados não sustentam, pois pontos não correspondidos também podem resultar de oclusão,
vegetação, alteração do campo de visão ou erro de registro. Variâncias móveis são calculadas usando somente o instante
corrente e o passado, de modo a impedir vazamento de informação futura.

### 2.6 Métricas de avaliação

As métricas primárias de trajetória são o Erro Absoluto de Trajetória (ATE) e o Erro Relativo de Pose (RPE). O ATE mede
a consistência global após alinhamento rígido com o GT. O RPE mede a deriva local entre poses separadas por um quadro ou
por 10 m de deslocamento. Como um erro pequeno pode ocultar interrupções frequentes, também são reportados cobertura,
número de falhas, número de reinicializações, duração e distância do maior trecho contínuo e fração elegível da trajetória.

Segmentos menores que 30 s ou 20 m não participam do ATE, embora continuem afetando a cobertura. Quando existem vários
segmentos elegíveis, o RMSE agregado é ponderado pelo número de poses. Essa regra reduz o risco de produzir ATE
artificialmente baixo por meio do alinhamento independente de muitos trechos curtos.

### 2.7 Reprodutibilidade e verificação

As dependências Python são fixadas em arquivo de *lock*. Os projetos C++ são associados a commits específicos, e todas
as alterações necessárias são armazenadas como patches versionados. Cada execução registra configuração, versão do
método, uso de IMU, decisão de *deskew* e diretório da tentativa. A promoção das saídas é atômica: uma tentativa com falha
não substitui um resultado válido anterior.

A suíte automatizada contém 115 testes. Além dos testes unitários, os executores de odometria visual possuem testes de
fumaça sintéticos, e a tabela final é submetida a um teste de contrato que verifica causalidade, papéis das colunas,
normalização de quatérnios e ausência de vazamento de atributos de avaliação para a entrada do modelo.

## 3. Resultados preliminares

### 3.1 Configuração dos experimentos de fumaça

Os experimentos iniciais utilizaram a sequência BotanicGarden 1018-00, com 147,8 s e GT, e um trecho de 60 s do
RELLIS-3D, sem associação verificável ao `poses.txt`. O experimento do BotanicGarden permite avaliar erro e continuidade.
O trecho do RELLIS verifica portabilidade entre sensores e formatos, mas, por não possuir GT compatível, permite avaliar
apenas cobertura e comportamento operacional.

### 3.2 Desempenho das odometrias isoladas

| Sequência | Método | ATE RMSE (m) | RPE translacional por quadro (m) | Cobertura | Falhas | Maior trecho contínuo (s) |
|---|---|---:|---:|---:|---:|---:|
| BotanicGarden 1018-00 | ORB-SLAM3 | 0,877 | 0,015 | 65,0% | 0 | 96,120 |
| BotanicGarden 1018-00 | Stella VSLAM | 1,135 | 0,016 | 65,0% | 0 | 96,120 |
| BotanicGarden 1018-00 | FAST-LIO2 | **0,047** | 0,016 | 77,8% | 1 | 114,981 |
| BotanicGarden 1018-00 | KISS-ICP | 0,132 | 0,024 | **99,9%** | 0 | **147,760** |
| RELLIS-3D, trecho de 60 s | ORB-SLAM3 | - | - | 83,6% | 0 | 1,700 |
| RELLIS-3D, trecho de 60 s | Stella VSLAM | - | - | 83,6% | 0 | 1,700 |
| RELLIS-3D, trecho de 60 s | FAST-LIO2 | - | - | 99,3% | 0 | 59,499 |
| RELLIS-3D, trecho de 60 s | KISS-ICP | - | - | **99,8%** | 0 | **59,799** |

Fonte: Elaborada pelo autor (2026).

No BotanicGarden, ORB-SLAM3 e Stella VSLAM cobriram 65,0% da sequência porque as imagens estéreo abrangem cerca de 96 s
dos 147,8 s disponíveis. Nos trechos cobertos, ambas mantiveram rastreamento contínuo, sem falha ou reinicialização. O
ORB-SLAM3 apresentou ATE de 0,877 m, enquanto Stella VSLAM apresentou 1,135 m. A proximidade dos respectivos RPEs
translacionais por quadro, 0,015 m e 0,016 m, indica comportamento local semelhante nesse experimento, embora o erro global
do ORB-SLAM3 tenha sido menor.

O FAST-LIO2 obteve o menor ATE, 0,047 m, e RPE translacional por quadro de 0,016 m. Sua cobertura de 77,8% é limitada pela
janela temporal da IMU Xsens, que começa aproximadamente 12,3 s após o LiDAR e termina por volta de 127,6 s. A única falha
contabilizada corresponde ao término dessa cobertura, não à perda de uma mensagem. O KISS-ICP alcançou a maior cobertura,
99,9%, e percorreu praticamente toda a sequência sem interrupção. Seu ATE de 0,132 m foi superior ao do FAST-LIO2, mas
inferior ao das duas odometrias visuais. A comparação deve considerar que FAST-LIO2 utiliza IMU, enquanto KISS-ICP utiliza
somente as nuvens de pontos.

No trecho do RELLIS-3D, não foram calculados ATE e RPE porque o exemplo de 60 s não pôde ser associado de forma inequívoca
a nenhuma das cinco sequências anotadas. FAST-LIO2 e KISS-ICP mantiveram cobertura próxima da totalidade do trecho. As
odometrias visuais apresentaram cobertura temporal de 83,6%, porém o maior trecho contínuo foi de apenas 1,7 s devido à
taxa efetiva e à idade máxima admitida para reutilização causal das poses. Esses resultados não permitem concluir qual
método é mais preciso no RELLIS-3D; demonstram apenas que os quatro executores processam os dados e produzem o contrato
esperado.

### 3.3 Investigação das perdas isoladas no FAST-LIO2

As primeiras execuções do FAST-LIO2 apresentaram perdas isoladas e não determinísticas. No BotanicGarden, três execuções
casaram 97,4%, 98,3% e 96,3% das varreduras cobertas pela IMU. No RELLIS-3D, as proporções foram 93,3%, 92,3% e 93,0%.
Os índices ausentes mudavam entre execuções, comportamento incompatível com uma falha determinística do conteúdo de uma
varredura.

A investigação separou as etapas de publicação, processamento e gravação. O número de poses internas produzidas pelo
FAST-LIO2 era igual ao número recebido pelo gravador, descartando perda na gravação da odometria. Em seguida, um assinante
ROS 2 vazio foi conectado ao replay do RELLIS-3D, cujas mensagens `PointCloud2` possuem aproximadamente 6 MiB. Com QoS
`best_effort`, foram recebidas 522 das 599 nuvens. Mantendo o mesmo experimento e alterando apenas o assinante para
`reliable`, foram recebidas 599 das 599 nuvens. A evidência localizou a perda antes do processamento do FAST-LIO2, na
entrega DDS do tópico LiDAR.

Foi então versionado um patch que substitui `SensorDataQoS`, configurado como `best_effort`, por QoS `reliable` com fila
de 100 mensagens. Após a correção, foram realizadas três execuções independentes em cada dataset. No BotanicGarden, as
três execuções produziram exatamente 1.141 poses para 1.143 varreduras cobertas pela IMU (99,83%); somente os dois primeiros
índices dessa janela não produziram pose devido à inicialização. No RELLIS-3D, as três execuções produziram exatamente 596
poses para 599 varreduras (99,50%); os únicos índices ausentes foram os três iniciais. A repetibilidade dos resultados e a
eliminação das lacunas intermediárias sustentam a conclusão de que os pulos isolados decorriam da política de QoS, e não
do algoritmo de estimação ou do gravador.

A correção elevou a cobertura oficial do FAST-LIO2 no BotanicGarden de 72,3% para 77,8%, reduziu as falhas de 41 para 1 e
aumentou o maior trecho contínuo de 8,5 s para aproximadamente 115 s. No RELLIS-3D, a cobertura passou de 92,5% para 99,3%,
as falhas foram reduzidas de 33 para zero e o maior trecho contínuo passou de 7,1 s para 59,5 s. O ATE do BotanicGarden
permaneceu em 0,047 m, indicando que a correção alterou a continuidade dos dados sem modificar a precisão das poses que já
eram produzidas.

### 3.4 Avaliação do *deskew* no KISS-ICP

O *deskew* compensa o movimento ocorrido durante a aquisição sequencial dos pontos de uma varredura. Os campos de tempo
por ponto foram validados quanto à unidade, duração aproximada de 100 ms e monotonicidade por anel. Apesar dessa validação,
habilitar a compensação piorou o desempenho do KISS-ICP nos dois sensores avaliados.

| Dataset | Configuração | ATE (m) | RPE translacional por quadro (m) |
|---|---|---:|---:|
| BotanicGarden 1018-00 | com *deskew* | 0,132 | 0,0409 |
| BotanicGarden 1018-00 | sem *deskew* | 0,132 | **0,0245** |
| RELLIS-3D, trecho de 60 s | com *deskew* | - | comparação secundária desfavorável |
| RELLIS-3D, trecho de 60 s | sem *deskew* | - | mais coerente com rodas e FAST-LIO2 |

Fonte: Elaborada pelo autor (2026).

No BotanicGarden, o ATE permaneceu inalterado, mas o RPE translacional por quadro aumentou de 2,45 cm para 4,09 cm com
*deskew*. No RELLIS-3D, a trajetória com compensação percorreu 66,9 m em 60 s, enquanto a trajetória sem compensação
percorreu 57,7 m. A odometria das rodas indica aproximadamente 56 m para o mesmo período, constituindo evidência externa
favorável à configuração sem compensação. A configuração sem *deskew* também apresentou maior correlação com as
velocidades translacional e angular do FAST-LIO2.

A causa física do comportamento ainda não foi demonstrada. A hipótese de que as nuvens já tenham sido compensadas pelos
drivers permanece não verificada e não deve ser apresentada como conclusão. Até que a causa seja identificada, o
*deskew* permanece desativado nos dois datasets porque essa decisão é sustentada pelas métricas observadas.

### 3.5 Associação entre o GT do RELLIS-3D e as varreduras da sequência 00000

**Objetivo.** Determinar se as 2.847 poses de `poses.txt`, que não possuem timestamps, podem ser associadas de forma
única às varreduras Ouster gravadas no arquivo da sequência 00000, condição necessária para utilizá-las como GT.

**Hipótese.** O protocolo preliminar previa associação por ordem, com a k-ésima pose correspondendo à k-ésima varredura.
O arquivo, contudo, contém 2.849 varreduras. Formulou-se a hipótese de que exatamente duas varreduras não possuem pose e
de que sua posição poderia ser identificada comparando o movimento descrito por `poses.txt` com sensores independentes.

**Procedimento.** Os critérios de aceitação foram fixados antes da análise: concordância entre odometria de rodas, IMU e
FAST-LIO2 quanto ao par de varreduras não associadas, com tolerância de uma varredura; estabilidade em reamostragem por
blocos; diferença no Critério de Informação Bayesiano (ΔBIC) superior a 10 em relação ao segundo candidato; e ausência de
mudança sistemática de fase. Odometria de rodas e duas IMUs (Microstrain e VectorNav) foram tratadas como evidências
primárias; o FAST-LIO2 foi empregado apenas como confirmação, para evitar circularidade entre a escolha da associação e a
avaliação posterior do método. Foram avaliados exaustivamente todos os 4.056.976 pares monotônicos de varreduras não
associadas, incluindo início, fim e interior da sequência. Para cada par, o incremento de pose entre poses consecutivas
foi comparado ao sinal do sensor integrado entre as varreduras associadas, e o custo foi definido como a soma dos
quadrados dos resíduos normalizados. Como todos os candidatos possuem o mesmo número de parâmetros, o ΔBIC equivale à
diferença de custo. O procedimento foi validado previamente com dados sintéticos de descartes conhecidos.

**Resultados.** Os timestamps das 2.849 varreduras não apresentaram lacunas, duplicatas ou inversões, com intervalos entre
99,3 ms e 100,9 ms. As poses indicam que o veículo permaneceu praticamente parado no início (até a pose 95) e no fim da
sequência. As três evidências primárias indicaram que nenhuma varredura deixa de ser associada durante o movimento, mas
não identificaram o par: os conjuntos com ΔBIC < 10 contêm de 5.778 a 6.903 pares, todos com as duas varreduras não
associadas no trecho inicial parado, e a margem para o segundo candidato variou de 0,004 a 0,85. As IMUs favoreceram o
deslocamento global de duas varreduras somente sob a suposição de latência nula entre seus timestamps e os da nuvem;
com latência livre, os deslocamentos de zero, uma e duas varreduras tornaram-se equivalentes (ΔBIC ≤ 6,3), com a
latência estimada variando em aproximadamente 100 ms por varredura deslocada. O FAST-LIO2, comparado por índice de
varredura e, portanto, independente de relógio, favoreceu o deslocamento de uma varredura, com uma varredura não
associada no início e outra no fim (ΔBIC de 131.887 contra o deslocamento de duas varreduras). A reamostragem por blocos
não reproduziu um par estável em nenhuma das evidências.

| Evidência | Par de melhor ajuste | Deslocamento durante o movimento | Margem para o 2º candidato (ΔBIC) |
|---|---|---:|---:|
| Odometria de rodas | (115, 116) | 2 | 0,85 |
| IMU Microstrain | (16, 27) | 2 | 0,01 |
| IMU VectorNav | (15, 16) | 2 | 0,004 |
| FAST-LIO2 (confirmação) | (9, 2738) | 1 | 0,46 |

Fonte: Elaborada pelo autor (2026).

**Discussão.** O resultado negativo decorre de duas limitações distintas. A primeira é a falta de identificabilidade dos
descartes dentro dos trechos em que o veículo está parado, pois qualquer posição nesses trechos produz o mesmo movimento
relativo. A segunda é a confusão entre o deslocamento global da associação e a latência dos sensores temporizados: um
deslocamento de uma varredura equivale a um atraso aparente de cerca de 100 ms. As evidências seriam compatíveis entre si
caso os timestamps das IMUs estivessem atrasados em aproximadamente 100 ms em relação ao timestamp da nuvem; essa
explicação, porém, foi formulada após a observação dos resultados e não foi testada.

**Ameaças à validade.** As métricas de classe e o teste de degenerescência entre deslocamento e latência foram
acrescentados após os primeiros resultados e têm caráter exploratório. Uma versão inicial do custo atribuía custo nulo a
intervalos sem dados do sensor, o que tornava os candidatos incomparáveis; o defeito foi corrigido antes dos resultados
reportados. A origem do `poses.txt` não é declarada e pode ser correlacionada a métodos LiDAR, o que afeta a
interpretação de métricas, mas não a comparação por índice.

**Decisão.** Os critérios de concordância, estabilidade e margem não foram atendidos, e o veredito C foi adotado como
definitivo para este protocolo. A associação não foi reaberta com testes adicionais, pois análises concebidas após a
observação dos resultados ampliariam os graus de liberdade da inferência. Em consequência, o GT por índice permanece
bloqueado no pipeline; o RELLIS-3D é utilizado sem rótulos, apenas para cobertura, continuidade, indicadores de qualidade
e avaliação exploratória, sem cálculo de ATE ou RPE contra `poses.txt`; e o BotanicGarden permanece como base
confirmatória com GT. Ficam registrados como trabalho futuro, sujeitos a novo protocolo, dois testes: o uso da IMU
interna do Ouster, que compartilha o relógio da nuvem e poderia esclarecer a latência, embora não identifique quais
varreduras foram omitidas nos trechos parados; e o registro direto das nuvens brutas com `poses.txt`, que verificaria a
consistência geométrica, mas não constituiria evidência plenamente independente caso as poses provenham de SLAM LiDAR.

**Rastreabilidade.** `docs/preflight_rellis.md` (seção de 15/10/2026), `tools/rellis_assoc.py`,
`tests/test_rellis_assoc.py` e `data/analysis/rellis_assoc/result.json`.

### 3.6 Sequências completas: BotanicGarden 1018-13 e RELLIS-3D 00000

**Objetivo.** Verificar o comportamento do pipeline e das odometrias isoladas em sequências completas: a sequência
BotanicGarden 1018-13, avaliada com GT de levantamento (`survey`) e de caráter confirmatório, e a sequência RELLIS-3D
00000, processada sem GT e de caráter não supervisionado e exploratório, em razão do veredito C (seção 3.5).

**Dados e configuração.** A sequência 1018-13 possui 208,8 s, 2.071 varreduras VLP-16, 1.600 pares estéreo e 1.938 poses
de GT, das quais resultaram 1.936 instantes da grade com GT. A sequência 00000 possui 284,9 s, 2.849 varreduras Ouster
OS1-64 e 3.068 pares estéreo, entregues a 10,77 Hz em média por uma câmera nominalmente de 15 Hz com descartes. Foram
empregadas as mesmas configurações, versões e correções das seções anteriores. Todos os processos terminaram sem nós
órfãos, e as tabelas resultantes satisfizeram o contrato de dados.

**Resultados no BotanicGarden 1018-13.**

| Método | ATE (m) | RPE transl. em 10 m (m) | RPE rot. em 10 m | Cobertura | Falhas | Reinic. | Maior trecho contínuo |
|---|---:|---:|---:|---:|---:|---:|---:|
| ORB-SLAM3 | 1,246 | 0,469 | 0,66° | 74,8% | 2 | 2 | 96,9 s / 121,0 m |
| Stella VSLAM | 1,601 | 0,586 | 0,68° | 76,4% | 0 | 0 | 100,4 s / 122,7 m |
| FAST-LIO2 | 0,067 | 0,100 | 0,80° | 87,6% | 1 | 0 | 183,1 s / 200,7 m |
| KISS-ICP | 1,827 | 0,250 | 3,06° | 100,0% | 0 | 0 | 208,8 s / 201,1 m |

Fonte: Elaborada pelo autor (2026). A cobertura tem como denominador os 2.071 instantes da grade LiDAR.

O FAST-LIO2 apresentou o menor erro, mas sua cobertura foi limitada pela IMU, que abrange as varreduras 131 a 1.948
(1.818 varreduras); dentro dessa janela, 1.816 varreduras receberam pose, e as duas ausentes correspondem à
inicialização. A única falha registrada é a transição no fim da cobertura da IMU. As odometrias visuais ficaram
restritas à janela das câmeras. O KISS-ICP manteve cobertura praticamente total, mas apresentou ATE de 1,83 m em 201 m,
valor muito superior ao observado na sequência 1018-00 (0,13 m em 115 m), e o maior erro rotacional entre os métodos.
A causa desse aumento não foi investigada e não deve ser inferida a partir destes dados.

**Correção da semântica temporal do casamento no FAST-LIO2.** Na primeira montagem, quatro varreduras consecutivas do
1018-13 (índices 1.810 a 1.813) apareceram sem pose, de forma idêntica em quatro execuções. Verificou-se que o FAST-LIO2
havia publicado poses para essas varreduras, mas com carimbo de tempo entre 5,6 ms e 7,0 ms anterior ao fim da varredura
adotado pelo pipeline, acima da tolerância de associação então utilizada (5 ms). O FAST-LIO2 carimba a odometria no
tempo do último ponto que permanece após seu pré-processamento, enquanto o pipeline define o fim da varredura pelo último
ponto válido da nuvem completa; trata-se, portanto, de dois conceitos distintos do mesmo instante. A tolerância foi
alterada para 20 ms porque o maior desvio observado nas quatro sequências foi de 7,02 ms, as poses consecutivas estão
separadas por pelo menos 96 ms e a associação é monotônica e um-para-um, de modo que janelas de ±20 ms não se sobrepõem.
A alteração corrige a semântica temporal do casamento e não constitui flexibilização destinada a aumentar
artificialmente a cobertura: a análise de sensibilidade com 5, 10 e 20 ms alterou somente essas quatro varreduras, e os
resultados com 10 ms e 20 ms foram idênticos; o ATE não foi utilizado na escolha e permaneceu inalterado. Com a correção,
a cobertura do FAST-LIO2 no 1018-13 passou de 87,4% para 87,6%, as falhas de 2 para 1 e o maior trecho contínuo de
169,0 s para 183,1 s; as demais sequências não se alteraram. O desvio observado passou a ser registrado em cada execução.

**Resultados no RELLIS-3D 00000 (não supervisionado).** Por não haver GT utilizável, não foram calculados ATE nem RPE, e
todas as colunas de GT da tabela permanecem vazias. O FAST-LIO2 produziu pose para 99,9% das varreduras (ausentes apenas
as três iniciais) e o KISS-ICP para 100,0%, ambos sem falhas, com trechos contínuos de 284,5 s e 284,8 s. As odometrias
visuais rastrearam todos os 3.068 quadros sem perda, mas apresentaram cobertura de 85,1% na grade LiDAR e trecho
contínuo máximo de 3,5 s. Essa descontinuidade não decorre de falha de rastreamento: nos intervalos de 133 ms entre
quadros, alguns instantes da grade de 10 Hz não recebem quadro novo, e o incremento correspondente é invalidado por
construção. Nesse dataset, portanto, o indicador de continuidade das odometrias visuais reflete a entrega da câmera, e
não a robustez do algoritmo.

**Ameaças à validade.** Os resultados do 1018-13 correspondem a uma única execução para as odometrias visuais e o
KISS-ICP; o FAST-LIO2 foi repetido quatro vezes, com resultados idênticos. O GT do BotanicGarden refere-se a um
levantamento cuja precisão declarada é a do mapa, não a de cada pose. Os resultados do RELLIS-3D não permitem
conclusões sobre exatidão.

**Decisão.** A tolerância de 20 ms foi adotada como padrão do pipeline, com registro do desvio em cada execução. O
BotanicGarden permanece como base confirmatória; o RELLIS-3D 00000 é incorporado apenas para cobertura, continuidade e
indicadores.

**Rastreabilidade.** `docs/RESULTS_sequences.md`, `data/output/metrics.csv`, `data/runs/1018-13/fastlio/run.json` e
`ofd/run_fastlio.py`.

## 4. Ameaças à validade

### 4.1 Validade do construto

ATE e RPE não representam isoladamente robustez operacional. Por esse motivo, a avaliação também considera cobertura,
falhas, reinicializações e continuidade. O FAST-LIO2 utiliza IMU, de modo que seu desempenho não pode ser atribuído apenas
ao LiDAR. O indicador de pontos sem correspondência não mede exclusivamente objetos dinâmicos e recebe denominação que
explicita essa limitação.

### 4.2 Validade interna

Erros de timestamp, frame ou entrega de mensagens podem ser confundidos com falha algorítmica. A mitigação inclui
sincronização causal, contratos explícitos de frame, validação do tempo por ponto, verificação de nós órfãos e teste de
QoS. O caso do FAST-LIO2 demonstra a relevância dessa ameaça: a infraestrutura de comunicação produzia falhas que seriam
atribuídas incorretamente ao estimador sem o experimento controlado.

### 4.3 Validade externa

Os resultados abrangem duas sequências com GT, ambas do BotanicGarden (1018-00 e 1018-13), e duas sem GT do
RELLIS-3D (trecho de 60 s e sequência 00000). Portanto, não permitem generalização para todos os ambientes externos,
condições climáticas ou configurações sensoriais, e a avaliação confirmatória restringe-se a um único ambiente e a um
único conjunto de sensores. A inclusão do RELLIS-3D amplia a diversidade apenas para cobertura, continuidade e
indicadores, e nenhum dos resultados substitui a validação no robô real.

### 4.4 Validade dos resultados

O FAST-LIO2 foi repetido três vezes em cada experimento após a correção de QoS, produzindo resultados idênticos. Os demais
métodos ainda não passaram pelo mesmo número de repetições em todas as sequências. O GT do RELLIS-3D não possui origem
metrológica explicitada e pode ser correlacionado a métodos LiDAR; por isso, a avaliação principal permanece no
BotanicGarden. Na sequência 00000, além disso, a associação entre poses e varreduras não pôde ser estabelecida de forma
única (seção 3.5), e a sequência não é utilizada com GT. Resultados de sequências em processamento não são
incorporados até que os contratos e as métricas sejam verificados.

## 5. Implicações para o modelo de fusão

Os experimentos mostram que precisão, disponibilidade e continuidade são propriedades distintas. FAST-LIO2 apresentou
o menor ATE no BotanicGarden, mas sua disponibilidade foi limitada pela cobertura da IMU. KISS-ICP apresentou erro global
maior, porém manteve cobertura praticamente total. As odometrias visuais apresentaram continuidade durante a janela de
imagens, mas ficaram indisponíveis no restante da sequência. Portanto, selecionar uma fonte apenas pelo menor erro médio
não atende ao objetivo de navegação robusta.

Esses resultados justificam fornecer ao modelo não somente incrementos de pose, mas também validade, idade, duração do
incremento, estado de rastreamento e indicadores de qualidade. Também justificam distinguir indisponibilidade sensorial,
falha de infraestrutura e degradação real do algoritmo. A futura avaliação da fusão deverá comparar a trajetória final
com cada fonte isolada e com estratégias de pesos fixos, conforme as hipóteses formuladas na dissertação.

## 6. Próximos experimentos

1. Investigar o aumento do ATE do KISS-ICP no BotanicGarden 1018-13 (1,83 m, contra 0,13 m no 1018-00).
2. Repetir as odometrias visuais e o KISS-ICP nas sequências completas para estimar a variabilidade entre execuções.
3. Investigar a causa física da degradação do KISS-ICP com *deskew*, sem alterar a decisão experimental já sustentada
   pelos resultados.
4. Definir, com os responsáveis pelo modelo, se a entrada utilizará \(\Delta T + \Delta t + age\), velocidade em
   \(\mathfrak{se}(3)\), ou ambas em estudo de ablação.

## Referências

CAMPOS, C. et al. ORB-SLAM3: An Accurate Open-Source Library for Visual, Visual-Inertial, and Multimap SLAM. *IEEE
Transactions on Robotics*, v. 37, n. 6, p. 1874-1890, 2021. Disponível em:
<https://doi.org/10.1109/TRO.2021.3075644>.

JIANG, P.; OSTEEN, P.; WIGNESS, M.; SARIPALLI, S. RELLIS-3D Dataset: Data, Benchmarks and Analysis. In: *IEEE
International Conference on Robotics and Automation*, 2021, p. 1110-1116. Disponível em:
<https://arxiv.org/abs/2011.12954>.

LIU, Y. et al. BotanicGarden: A High-Quality Dataset for Robot Navigation in Unstructured Natural Environments. *IEEE
Robotics and Automation Letters*, v. 9, n. 3, p. 2798-2805, 2024. Disponível em:
<https://doi.org/10.1109/LRA.2024.3359548>.

SUMIKURA, S.; SHIBUYA, M.; SAKAMOTO, K. OpenVSLAM: A Versatile Visual SLAM Framework. In: *ACM International
Conference on Multimedia*, 2019. Disponível em: <https://arxiv.org/abs/1910.01122>.

VIZZO, I. et al. KISS-ICP: In Defense of Point-to-Point ICP - Simple, Accurate, and Robust Registration If Done the
Right Way. *IEEE Robotics and Automation Letters*, v. 8, n. 2, p. 1029-1036, 2023. Disponível em:
<https://doi.org/10.1109/LRA.2023.3236571>.

XU, W. et al. FAST-LIO2: Fast Direct LiDAR-Inertial Odometry. *IEEE Transactions on Robotics*, v. 38, n. 4,
p. 2053-2073, 2022. Disponível em: <https://doi.org/10.1109/TRO.2022.3141876>.

## Rastreabilidade dos resultados

- Resultados numéricos e condições dos experimentos: `docs/RESULTS_smoke.md`.
- Investigação do *deskew*: `docs/deskew_rellis.md`.
- Associação do GT do RELLIS-3D (preliminar e sequência 00000): `docs/preflight_rellis.md`, `tools/rellis_assoc.py`,
  `data/analysis/rellis_assoc/result.json`.
- Contrato de dados, decisões e riscos: `docs/superpowers/specs/2026-10-14-odom-fusion-dataset-design.md`.
- Sequências completas e tolerância do casamento do FAST-LIO2: `docs/RESULTS_sequences.md`.
- Estado reproduzível do código após revisão: commits `7db3804` e `2c35918`.
