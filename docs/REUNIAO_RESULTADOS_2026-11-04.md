# Reunião sobre os resultados do mestrado — 04/11/2026

## Resumo executivo

O núcleo técnico e experimental do mestrado foi concluído. Foi construído um pipeline causal e reproduzível para
combinar quatro fontes de odometria, foram comparadas estratégias simples, clássicas e aprendidas, e os modelos
congelados foram avaliados cegamente em oito sequências externas de três dias.

A principal hipótese sobre a CNN temporal não se confirmou no teste externo. A CNN foi melhor que a média simples em
erro angular em apenas uma das oito sequências e apresentou piora mediana também no erro linear e na deriva de 10 m.
Descritivamente, o filtro de Kalman apresentou menor erro angular que a média nas oito sequências, mas essa comparação
não havia sido definida como hipótese confirmatória antes da abertura.

A contribuição central do mestrado não depende de uma rede “vencedora”. O trabalho construiu uma forma rigorosa de
investigar fusão de odometrias e mostrou que ganhos observados durante o desenvolvimento podem não se generalizar para
outros dias.

## 1. Pergunta do projeto

O projeto investiga como combinar diferentes estimativas de movimento de um robô em ambiente natural. As fontes
possuem sensores e modos de falha distintos:

- ORB-SLAM3: odometria principalmente visual;
- Stella VSLAM: odometria principalmente visual;
- FAST-LIO2: odometria LiDAR-inercial;
- KISS-ICP: odometria LiDAR.

A pergunta experimental é se modelos que utilizam validade, indicadores de qualidade e histórico temporal conseguem
produzir uma fusão que se generalize melhor que estratégias simples e filtros clássicos.

## 2. O que foi construído

- Pipeline das quatro odometrias.
- Sincronização causal: cada instante usa somente presente e passado.
- Tabela comum com velocidades, validade, idade e indicadores das fontes.
- Separação explícita entre features, alvos de treinamento e avaliação.
- Contratos automáticos para timestamps, frames, schemas e ausência de vazamento de GT.
- Métricas de velocidade e trajetória.
- Modo cego que processa sequências externas sem ler o GT.
- Manifestos com hashes para proteger código, configurações, pesos, features e predições.
- Rotina de abertura única dos GTs.

## 3. Estratégias comparadas

- B5/T1: média causal das fontes válidas.
- T2: filtro de Kalman de velocidade.
- STEP: rede que calcula pesos usando o instante atual.
- MLP-W: rede com uma janela causal do histórico.
- CNN-W: rede convolucional temporal causal.
- LSTM-W: avaliada durante a seleção, mas não escolhida para o teste externo.

CNN, STEP e MLP-W foram treinadas com cinco sementes. Os modelos finais foram ajustados apenas nas duas sequências de
desenvolvimento e congelados antes de processar qualquer sequência externa.

## 4. Divisão dos dados

### Desenvolvimento

- `1018-00`;
- `1018-13`.

Essas sequências foram usadas para implementação, escolha da janela, configurações, orçamentos de treino, seleção da
CNN e ajuste do Kalman. Como seus resultados foram consultados durante o desenvolvimento, elas não fornecem evidência
externa independente.

### Teste externo

Oito sequências pertencentes a três dias:

- dia 1005: `1005-00`, `1005-01`, `1005-05`, `1005-07`;
- dia 1006: `1006-01`, `1006-03`;
- dia 1008: `1008-01`, `1008-03`.

## 5. Como funcionou o teste cego

Antes de abrir os GTs externos:

1. código, configurações e modelos foram congelados;
2. os pesos das cinco sementes foram salvos e registrados por hash;
3. as oito sequências foram processadas sem acesso ao GT;
4. as predições de todos os modelos foram gravadas;
5. manifestos de features e predições foram auditados;
6. confirmou-se que não havia alvos, erros ou métricas nas tabelas cegas;
7. os oito GTs ainda estavam lacrados.

Depois de autorização explícita, os GTs foram abertos uma única vez. A abertura produziu 144 avaliações: 18 saídas
de predição em oito sequências. Não houve métrica primária ausente. Ao final, os oito arquivos originais de GT foram
relacrados com modo `000`.

## 6. Evolução da hipótese

A hipótese original exigia que o modelo temporal superasse a média simples e o modelo por passo em velocidade linear
e angular, sem degradar a trajetória.

O gate de desenvolvimento mostrou que essa hipótese era inviável: a CNN ficou pior que STEP nas duas métricas e pior
que a média no erro linear. Esse resultado foi registrado antes do teste externo.

Ainda no desenvolvimento, a CNN apresentou ganho angular contra a média. Antes de processar as oito sequências
externas, foi registrada uma hipótese mais estreita, H1':

> A CNN selecionada reduz o RMSE angular em relação à média simples B5/T1 nas sequências externas.

Para ser positiva, a melhora mediana precisava ser maior que zero no conjunto das oito sequências e separadamente nos
três dias. RMSE linear e RPE de 10 m foram mantidos como guardas descritivas, sem margem escolhida depois dos dados.

## 7. Resultado principal

A H1' foi **negativa**.

- A CNN teve menor erro angular em apenas **1 das 8 sequências**.
- Seu erro angular foi **3,63% maior em mediana** que o da média B5/T1.
- As medianas dos dias 1005, 1006 e 1008 também foram desfavoráveis.
- Seu erro linear foi **1,92% maior em mediana**.
- Seu RPE translacional de 10 m foi **14,15% maior em mediana**.

Em desenvolvimento, a CNN havia apresentado ganhos angulares de aproximadamente 20,0% e 11,3% nas duas dobras. O
teste externo mostrou que esse padrão não se repetiu em outros dias.

## 8. Resultado descritivo do Kalman

O T2/Kalman apresentou:

- erro angular menor que a média simples nas **8 das 8 sequências**;
- redução angular relativa mediana de **6,88%**;
- erro linear **2,15% maior em mediana**;
- RPE translacional de 10 m **8,08% maior em mediana**.

Formulação correta para a reunião:

> Descritivamente, o filtro de Kalman apresentou menor erro angular que a média simples nas oito sequências externas,
> indicando uma direção promissora, mas ainda não confirmatória.

Não se deve afirmar que o Kalman é o “melhor modelo” ou que superou confirmatoriamente as redes. Essa hipótese não foi
registrada antes da abertura. Um teste confirmatório de T2 exigiria novo protocolo e dados independentes.

## 9. O que o resultado significa

- Aumentar a complexidade do modelo não garantiu generalização.
- Uma melhora nas sequências de desenvolvimento não foi suficiente para prever desempenho em outros dias.
- A média simples foi um baseline forte.
- O processamento cego impediu ajustes posteriores para favorecer um modelo.
- O resultado negativo é uma conclusão científica válida, não uma falha operacional.
- Cinco sementes mediram variabilidade do treinamento das redes, mas não a variabilidade de reexecutar as fontes
  visuais.

O resultado não significa que toda rede temporal seja inadequada, nem que o Kalman seja universalmente superior. A
conclusão vale para os modelos, configurações, sequências, ambiente e plataforma avaliados.

## 10. Contribuições do mestrado

### Técnica

Pipeline causal, verificável e reproduzível para combinar odometrias visuais, LiDAR e LiDAR-inerciais, incluindo
disponibilidade e indicadores de qualidade.

### Experimental

Comparação controlada entre média simples, filtragem clássica e modelos aprendidos, com separação entre desenvolvimento
e teste, cinco sementes, congelamento de artefatos e abertura única de GT.

### Científica

Evidência de que o ganho de modelos temporais observado no desenvolvimento não necessariamente se generaliza entre
dias. O estudo demonstra a importância de baselines fortes e avaliação externa cega.

## 11. Tese central proposta

> Em ambientes naturais, a fusão causal de odometrias heterogêneas exige mais do que aumentar a complexidade do
> modelo. Embora modelos aprendidos possam apresentar ganhos durante o desenvolvimento, esses ganhos podem não se
> repetir em outros dias. Baselines simples e clássicos, avaliados por um pipeline cego e reproduzível, são essenciais
> para distinguir uma melhoria que realmente se generaliza de um resultado ajustado às sequências conhecidas.

Em linguagem simples:

> Construímos uma forma rigorosa de investigar fusão de odometrias e descobrimos que uma rede mais complexa não
> garantiu melhor generalização.

## 12. Estado atual do projeto

- O núcleo experimental está concluído.
- Nada está sendo treinado ou processado neste momento.
- Os GTs externos estão relacrados.
- A suíte completa passou: 370 testes.
- Os resultados e manifestos foram auditados.
- O GitHub está atualizado até o commit `8420f39`.
- A explicação ampliada da tese central está em um commit local posterior.

## 13. Decisões importantes para a reunião

1. O núcleo experimental atual é suficiente para a dissertação e para a defesa?
2. Existe alguma validação adicional obrigatória, e qual lacuna científica ela responderia?
3. É necessário testar outro ambiente ou plataforma, ou isso pode ser assumido como limitação e trabalho futuro?
4. O comportamento do Kalman deve motivar um estudo novo com dados independentes ou permanecer como trabalho futuro?
5. O pacote público do dataset e do pipeline faz parte das entregas obrigatórias do mestrado?
6. Qual deve ser o peso relativo, na dissertação, da contribuição de engenharia, do protocolo cego e do resultado
   experimental negativo?

Qualquer novo experimento deve responder a uma lacuna definida antes de sua execução. Ele não deve servir para
substituir ou procurar um resultado mais favorável que o teste externo já concluído.

## 14. Versão curta para apresentação oral

> O projeto construiu um pipeline para combinar quatro odometrias diferentes de forma causal e reproduzível. Nós
> comparamos média simples, Kalman e três famílias de redes. As configurações foram escolhidas em duas sequências de
> desenvolvimento e depois congeladas. Em seguida, processamos oito sequências de outros três dias sem acessar o GT,
> gravamos todas as predições e só então fizemos uma abertura única. A CNN tinha mostrado ganho angular no
> desenvolvimento, mas no teste externo foi melhor em apenas uma das oito sequências e ficou pior também no erro
> linear e na deriva. O Kalman apresentou menor erro angular nas oito sequências, mas isso é um resultado descritivo,
> porque não era nossa hipótese confirmatória. A principal conclusão é que aumentar a complexidade e usar histórico
> aprendido não garantiu generalização. O valor do trabalho está tanto no pipeline e no protocolo cego quanto em
> demonstrar honestamente essa diferença entre desenvolvimento e teste externo. Agora precisamos decidir se esse
> núcleo já fecha o mestrado ou se existe alguma validação adicional realmente necessária.

## 15. Documentos para consulta durante a reunião

- `docs/TESE_CENTRAL_MESTRADO.md`: explicação completa da tese central.
- `docs/RESULTS_phase4_external.md`: números e tabelas do teste externo.
- `docs/RELATO_ACADEMICO_PIPELINE.md`: histórico acadêmico de todo o pipeline.
- `docs/RESULTS_phase3_pilot.md`: seleção formal dos modelos.
- `docs/amendment_phase4_hypothesis.md`: regra da H1' registrada antes do teste externo.
- `docs/ESTADO.md`: estado geral do repositório.
