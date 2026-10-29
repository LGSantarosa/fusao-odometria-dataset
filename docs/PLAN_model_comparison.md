# Plano de estudo — comparação de arquiteturas para fusão de odometrias

> **RASCUNHO DE PLANEJAMENTO — 29/10/2026.** Este documento ainda não é um protocolo pré-registrado, não autoriza
> abrir um novo conjunto de teste e não altera o experimento já concluído em `docs/protocol_fusion_model.md`. Decisões
> marcadas como **A DEFINIR** precisam ser fechadas com o orientador antes da execução confirmatória.

## 1. Ideia do artigo

Pergunta central proposta:

> Modelos temporais causais melhoram a fusão de odometrias heterogêneas em percursos não vistos, especialmente quando
> a qualidade ou a disponibilidade das fontes muda ao longo do tempo?

O estudo terá duas comparações complementares:

1. **Comparação das fontes:** ORB-SLAM3, Stella VSLAM, FAST-LIO2 e KISS-ICP isoladamente e em combinações simples.
2. **Comparação dos modelos de fusão:** métodos sem aprendizado, ridge, MLP, CNN 1D causal, LSTM e, separadamente,
   BiLSTM offline, todos avaliados sobre entradas e divisões equivalentes.

O primeiro experimento de fusão já comparou as quatro odometrias, a média das fontes válidas, ridge e duas MLPs. O
novo estudo deve preservar esse resultado como evidência anterior e ampliar a pergunta para o uso explícito do histórico
temporal. Ele não deve reescrever nem substituir o protocolo anterior.

## 2. O que cada comparação responde

| Eixo | Comparação | Pergunta respondida |
|---|---|---|
| Fonte | quatro odometrias isoladas | Qual fonte é mais precisa, disponível e contínua em cada condição? |
| Fusão simples | média das válidas e ridge | Combinar fontes já ajuda sem uma rede temporal? |
| Encoder causal | MLP por passo, MLP com janela, CNN 1D causal e LSTM | O histórico melhora a fusão em percurso não visto? |
| Cabeça de saída | ponderação das fontes e regressão direta | A restrição interpretável de pesos ajuda ou limita? |
| Referência offline | BiLSTM | Quanto o acesso a contexto futuro pode melhorar uma análise não embarcada? |
| Ablação de fonte | todas, retirada de uma e grupos por modalidade | De quais odometrias cada modelo realmente depende? |
| Robustez | perda de fonte no teste, sem retreino | Como o modelo reage a indisponibilidade não planejada? |

Não se deve misturar os dois sentidos de “melhor”. Uma odometria pode ter menor erro médio e cobertura limitada; um
modelo pode ter menor erro e latência incompatível com o robô. O artigo deverá declarar previamente como precisão,
robustez e custo computacional entram na conclusão.

## 3. Matriz de modelos proposta

### 3.1 Baselines preservados

- **B1–B4:** ORB-SLAM3, Stella VSLAM, FAST-LIO2 e KISS-ICP isoladamente, com a mesma retenção causal já definida.
- **B5:** média simples das fontes válidas.
- **B6:** regressão ridge sobre as 56 entradas atuais.
- **F1:** MLP por passo que produz quatro pesos mascarados por validade.
- **F2:** MLP por passo que prediz diretamente as seis componentes da velocidade.

### 3.2 Novos encoders

Cada encoder causal deverá ser testado, quando aplicável, com as mesmas duas cabeças de saída:

- **Cabeça W — ponderação:** quatro logits, máscara de validade, softmax e combinação convexa dos twists válidos.
- **Cabeça D — direta:** seis componentes de velocidade em se(3).

| Encoder | Contexto | Cabeças | Papel |
|---|---|---|---|
| MLP por passo | somente a linha atual | W e D | referência já executada (F1/F2) |
| MLP com janela achatada | mesma janela passada dos modelos temporais | W e D | separa ganho de contexto de ganho da arquitetura |
| CNN 1D causal | janela passada, sem preenchimento com futuro | W e D | padrões locais e inferência paralelizável |
| LSTM | histórico passado | W e D | dependências temporais e estado recorrente |
| BiLSTM | passado e futuro | W e D | referência offline, fora da disputa principal embarcada |

A MLP com janela é um controle necessário: comparar apenas a MLP por passo com CNN/LSTM confundiria “ter histórico”
com “usar uma arquitetura temporal”. O tamanho da janela, a forma de reinicializar estados e as faixas de capacidade
dos modelos serão escolhidos somente com dados de desenvolvimento e depois congelados.

### 3.3 Posição da BiLSTM

A BiLSTM padrão usa amostras futuras em relação ao instante previsto. Por isso:

- será rotulada explicitamente como **offline**;
- não poderá vencer nem substituir o modelo causal destinado à navegação em tempo real;
- seus números ficarão em uma tabela separada ou em uma coluna marcada como não causal;
- qualquer variante de BiLSTM limitada a uma janela somente passada deverá receber outro nome e outra justificativa,
  para não esconder a diferença operacional.

## 4. Perguntas de pesquisa candidatas

- **RQ1 — fontes:** como precisão, cobertura e continuidade variam entre as quatro odometrias?
- **RQ2 — temporalidade:** CNN 1D causal ou LSTM supera a MLP por passo e a MLP com a mesma janela?
- **RQ3 — saída:** ponderar twists válidos é mais estável do que regredir a velocidade diretamente?
- **RQ4 — contribuição:** quais fontes explicam o ganho de cada arquitetura e quais são redundantes?
- **RQ5 — robustez:** o modelo mantém desempenho quando uma fonte fica indisponível sem aviso?
- **RQ6 — implantação:** qual é a relação entre erro, latência, memória e número de parâmetros no hardware-alvo?

Antes do teste confirmatório será preciso escolher uma hipótese primária e uma regra de decisão. Não é válido testar
todas as arquiteturas, escolher a vencedora olhando o teste e depois apresentá-la como hipótese confirmada. Duas opções
aceitáveis para discussão com o orientador são:

1. escolher um modelo principal apenas pela validação interna e avaliar uma única comparação confirmatória; ou
2. manter várias comparações confirmatórias, com ordem hierárquica ou correção de multiplicidade pré-definida.

## 5. Dados e limite atual

### 5.1 Uso dos dados existentes

- `1018-00` e `1018-13` já foram abertas e analisadas no primeiro experimento. Podem servir ao desenvolvimento,
  depuração e estudo piloto, mas não constituem um teste totalmente novo para hipóteses formuladas depois de seus
  resultados.
- `rellis_example` e `00000` não têm GT validado e continuam restritas a inferência descritiva.
- Nenhuma linha deve ser embaralhada aleatoriamente entre treino e teste; a unidade externa é a sequência.

### 5.2 Condição para uma afirmação confirmatória nova

Antes de congelar o protocolo, deverá ser decidido com o orientador se o artigo terá:

- novas sequências BotanicGarden ainda não usadas;
- uma segunda base com GT validado e as quatro fontes executáveis; ou
- avaliação no robô com referência externa adequada.

Sem novos dados com GT, o trabalho pode produzir um benchmark piloto e uma análise metodológica, mas não deve vender
as duas sequências já vistas como confirmação independente de uma hipótese criada depois delas. A quantidade mínima de
sequências e o tipo de generalização pretendido são **A DEFINIR**; a sequência, e não cada scan, deve ser tratada como
unidade independente para inferência estatística.

## 6. Divisão e prevenção de vazamento

Desenho proposto:

1. **Conjunto de desenvolvimento:** implementação, escolha de janela, capacidade e hiperparâmetros.
2. **Validação interna:** blocos temporais contíguos somente dentro das sequências de desenvolvimento.
3. **Teste externo bloqueado:** sequências inteiras não usadas para escolher arquitetura, janela, hiperparâmetros ou
   regra de decisão.

Regras obrigatórias:

- normalização, imputação, seleção de hiperparâmetros e número de épocas ajustados somente no treino;
- janelas nunca atravessam o início ou o fim de uma sequência;
- CNN e LSTM causais nunca recebem linha posterior ao instante previsto;
- a purga deve cobrir o maior campo receptivo entre a janela do modelo e a variância causal de 10 passos já presente
  nas entradas; a fórmula exata será validada por teste antes de ser congelada;
- escolha do tamanho de contexto feita apenas na validação interna;
- nenhum resultado do teste externo pode provocar mudança de modelo ou protocolo;
- falhas, emendas e repetições ficam registradas, sem apagar execuções inválidas.

Um teste automatizado deverá alterar todo o futuro de uma sequência e confirmar que as predições causais anteriores
permanecem idênticas. Outro deverá confirmar que nenhuma janela de treino compartilha o campo receptivo proibido com a
validação após a purga.

## 7. Condições de comparação justa

Todos os modelos causais devem compartilhar:

- as mesmas 56 entradas por passo e as mesmas máscaras de validade;
- os mesmos alvos `gt_vx … gt_wz`;
- as mesmas sequências, linhas elegíveis e divisões externas;
- o mesmo ajuste de normalização restrito ao treino;
- a mesma perda principal ou uma transformação matematicamente equivalente;
- o mesmo conjunto de sementes e uma política equivalente de seleção;
- faixas sobrepostas de número de parâmetros e orçamento de otimização;
- medição no mesmo hardware e com o mesmo tamanho de lote para latência.

As diferenças inevitáveis deverão ser reportadas, não escondidas: a MLP por passo não tem contexto; a MLP com janela
tem entrada maior; a LSTM mantém estado; a CNN usa campo receptivo fixo; e a BiLSTM acessa o futuro.

## 8. Comparação das odometrias dentro dos modelos

O desenho separa dois experimentos, pois eles respondem perguntas diferentes.

### 8.1 Ablação com retreino — contribuição de informação

O modelo é treinado novamente em cada condição:

- quatro fontes;
- sem ORB-SLAM3;
- sem Stella VSLAM;
- sem FAST-LIO2;
- sem KISS-ICP;
- somente as duas fontes visuais;
- somente a família baseada em LiDAR (`FAST-LIO2 + KISS-ICP`, lembrando que FAST-LIO2 também usa IMU).

Isso mede quanto cada fonte acrescenta quando o modelo sabe, desde o treino, quais fontes existirão.

### 8.2 Perda de fonte sem retreino — robustez operacional

O modelo é treinado com as quatro fontes e, no teste, uma fonte é mascarada a partir de instantes pré-definidos. Isso
mede reação a uma indisponibilidade inesperada. Duração, posição e frequência das perdas deverão ser sorteadas ou
fixadas sem olhar o erro e registradas antes da execução.

Executar todas as ablações para todos os modelos pode tornar o estudo grande e multiplicar hipóteses. A versão mínima
recomendada é comparar todos os modelos com quatro fontes e executar as ablações completas apenas no modelo principal,
na MLP de referência e na média simples. O escopo final é **A DEFINIR**.

## 9. Métricas

### 9.1 Primárias candidatas

- RMSE vetorial da velocidade linear, em m/s;
- RMSE vetorial da velocidade angular, em rad/s.

A regra deverá dizer antecipadamente se ambas precisam melhorar, se existe margem mínima e como tratar múltiplas
sequências e sementes. O critério do primeiro experimento pode ser reutilizado ou substituído, mas qualquer mudança
precisa de justificativa anterior ao teste.

### 9.2 Secundárias

- RMSE das seis componentes;
- RPE em janelas de distância e ATE após integração causal;
- desempenho por quantidade e identidade das fontes válidas;
- erro imediatamente antes, durante e depois da perda de uma fonte;
- tempo de recuperação após retorno da fonte;
- pesos médios e sua estabilidade, para cabeças W;
- dispersão entre sementes;
- latência por passo, frequência sustentada, memória e número de parâmetros.

ATE e RPE não substituirão as primárias sem uma nova regra explícita. Scans sucessivos são correlacionados; milhares de
linhas não devem ser apresentados como milhares de amostras independentes. Intervalos de confiança e testes estatísticos
deverão respeitar sequência/bloco como unidade e ter utilidade apenas se houver sequências suficientes.

## 10. Plano de implementação e validação

### Fase 0 — decisões de escopo

- definir objetivo online principal e papel offline da BiLSTM;
- escolher dados adicionais com GT e hardware-alvo;
- decidir matriz mínima de modelos e ablações;
- definir hipótese principal e tratamento de multiplicidade.

### Fase 1 — infraestrutura, sem teste externo

- criar construtor de janelas causais e estados por sequência;
- separar encoder da cabeça W/D em uma API comum;
- implementar MLP com janela, CNN 1D causal, LSTM e BiLSTM offline;
- preservar F1/F2 atuais como referência reproduzível;
- gravar configuração, semente, versão e hashes em cada artefato.

### Fase 2 — testes sintéticos e de contrato

- teste de não uso do futuro;
- teste de isolamento entre sequências;
- teste da purga para o campo receptivo completo;
- teste de máscara e pesos nulos para fontes inválidas;
- teste de equivalência das métricas entre arquiteturas;
- tarefa sintética em que o alvo depende de histórico conhecido, para verificar se CNN/LSTM conseguem aprendê-lo;
- teste de determinismo por semente e registro de falhas.

### Fase 3 — piloto nos dados já vistos

- estimar custo, estabilidade e faixas plausíveis de janela/capacidade;
- identificar erros de implementação;
- não usar o piloto como confirmação nem esconder resultados desfavoráveis;
- congelar código e decisões que não dependem do novo teste.

### Fase 4 — revisão e protocolo

- obter revisão externa do plano;
- resolver críticas de vazamento, comparabilidade e escopo;
- escrever um novo `docs/protocol_*.md` com hipótese, grades, sementes e regra de decisão;
- registrar commit do protocolo antes do teste confirmatório.

### Fase 5 — execução bloqueada

- validação interna e seleção apenas no desenvolvimento;
- auditoria dos artefatos antes de liberar o teste;
- uma execução da fase confirmatória conforme o protocolo;
- registro do resultado positivo, negativo ou inconclusivo sem reinterpretar a regra.

## 11. Artefatos previstos

O novo estudo não deverá sobrescrever `data/analysis/fusion/`. Sugestão:

```text
data/analysis/model_comparison/
  phase1/<fold>/<model>/cv.csv
  phase1/<fold>/<model>/selected.json
  phase2/test_metrics.csv
  phase2/source_ablations.csv
  phase2/source_dropout.csv
  phase2/efficiency.csv
  phase2/predictions/
  decision.json
```

Documentos previstos:

- plano atual, mantido como histórico;
- novo protocolo pré-registrado;
- relatório operacional de cada fase;
- resultado final com tabelas por sequência e semente;
- manifesto dos artefatos e ambiente reproduzível.

## 12. Possível contribuição do artigo

Uma narrativa defensável, condicionada aos dados, seria:

1. benchmark sincronizado de quatro odometrias heterogêneas;
2. comparação controlada entre fusão instantânea e temporal;
3. separação explícita entre modelos causais implantáveis e referência offline;
4. ablação de contribuição e teste de perda inesperada de fontes;
5. análise conjunta de erro, disponibilidade e custo computacional.

Título de trabalho:

> **Causal Temporal Fusion of Heterogeneous Odometry Sources under Intermittent Availability**

Não deverão ser feitas, sem nova evidência, alegações de generalização entre sensores, ambientes ou robôs. O resultado
negativo do primeiro experimento faz parte da motivação e deve permanecer visível: ele mostra por que o histórico e o
desenho da fusão precisam ser testados, não que um resultado positivo futuro esteja garantido.

## 13. Decisões para a próxima reunião

1. O artigo é prioritariamente sobre navegação online? Se sim, BiLSTM fica apenas como referência offline.
2. Quais novas sequências com GT podem ser mantidas realmente bloqueadas?
3. Qual hardware representa a implantação e qual limite de latência/memória importa?
4. A comparação principal usa cabeça W, D ou ambas com correção de multiplicidade?
5. Quais ablações cabem no artigo sem diluir a pergunta central?
6. O artigo apresenta um modelo principal ou um benchmark sem declarar um vencedor único?
