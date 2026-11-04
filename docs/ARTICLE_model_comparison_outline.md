# Roteiro do artigo — fusão temporal de odometrias com avaliação cega

**Estado:** primeiro esqueleto após o fechamento do teste externo G1, em 04/11/2026. Este documento organiza a
narrativa e os artefatos já produzidos; não redefine hipóteses nem autoriza novas análises no teste aberto.

## 1. Ideia central em uma frase

Uma vantagem angular observada ao desenvolver fusão temporal aprendida em duas sequências não se generalizou para
oito sequências de outros três dias, enquanto um filtro clássico apresentou comportamento angular consistente em uma
comparação descritiva; um protocolo cego e uma abertura única tornaram essa diferença verificável sem seleção pelo
teste.

## 2. Títulos de trabalho

Opção principal:

> **Learned Temporal Fusion versus Classical Filtering for Heterogeneous Odometry: A Blind Evaluation Across Days**

Opção centrada no resultado:

> **When Development Gains Do Not Generalize: Blind Evaluation of Learned Temporal Odometry Fusion**

O primeiro título é mais neutro. O segundo comunica melhor o achado, mas deve ser usado somente se o texto mantiver
claro que a conclusão se restringe às configurações, à plataforma e ao ambiente avaliados.

## 3. Pergunta e resposta

**Pergunta original:** o uso explícito de histórico causal melhora a fusão de fontes heterogêneas além de um modelo
por passo e de baselines clássicos, em sequências de outros dias?

**Resposta do gate:** a hipótese conjunta original era inviável já no desenvolvimento, porque a CNN não superou STEP
nem B5 nas duas componentes de velocidade. Esse resultado foi registrado antes do teste externo.

**Pergunta externa emendada (H1'):** a CNN selecionada reduz o RMSE angular contra B5/T1 nas oito sequências externas?

**Resposta externa:** não. O efeito mediano foi -3,63%, apenas uma de oito sequências favoreceu a CNN, e os três dias
tiveram medianas negativas. A CNN também aumentou o RMSE linear em 1,92% e o RPE translacional de 10 m em 14,15%.

## 4. Contribuições sustentáveis

1. Um protocolo causal e reproduzível para comparar quatro fontes de odometria, modelos aprendidos e filtros clássicos
   sem usar GT como entrada ou critério de seleção externa.
2. Um fluxo cego auditável, com congelamento de código e modelos, manifestos com SHA-256 e abertura única de oito GTs.
3. Uma comparação controlada entre média causal, Kalman de velocidade, modelo por passo, MLP com janela e CNN causal,
   incluindo cinco sementes para cada modelo aprendido.
4. Evidência externa de que o ganho angular da CNN no desenvolvimento não se generalizou aos três dias externos.
5. Um resultado descritivo que motiva investigação futura: T2 apresentou RMSE angular menor que B5 nas oito
   sequências, mas esse contraste não foi pré-registrado como hipótese confirmatória.

Não são contribuições sustentadas: superioridade geral do Kalman, inferioridade universal de redes, generalização a
outros ambientes ou sensores, nem uma explicação causal para a diferença entre desenvolvimento e teste.

## 5. Resumo preliminar

A fusão de odometrias heterogêneas pode explorar fontes com precisão, disponibilidade e modos de falha distintos, mas
modelos aprendidos podem se ajustar a padrões específicos das sequências de desenvolvimento. Este trabalho compara
fusão por média, filtragem clássica e modelos neurais causais usando quatro fontes de odometria em um protocolo com
separação por sequência. Duas sequências foram usadas para desenvolvimento, seleção de arquitetura e treinamento
final; oito sequências de outros três dias foram processadas sem acesso ao *ground truth*, com código e pesos
congelados e abertura única auditada. A hipótese externa pré-registrada exigia que uma CNN causal reduzisse o RMSE
angular contra a média simples no conjunto e separadamente em cada dia. A CNN foi favorável em uma de oito sequências
e apresentou piora relativa mediana de 3,63% no RMSE angular, 1,92% no RMSE linear e 14,15% no RPE translacional de
10 m. Em análise descritiva, um filtro de Kalman reduziu o RMSE angular contra a média nas oito sequências, com ganho
mediano de 6,88%, acompanhado de piora linear e de trajetória. Os resultados mostram que ganhos neurais observados no
desenvolvimento não implicam transferência entre dias e destacam a importância de baselines clássicos fortes,
separação externa e avaliação cega em estudos de fusão de odometrias.

## 6. Estrutura proposta

### 6.1 Introdução

- problema: nenhuma fonte de odometria domina simultaneamente precisão, cobertura e continuidade;
- motivação: fusão temporal pode usar histórico e indicadores, mas aumenta capacidade e risco de sobreajuste;
- lacuna: comparações sem separação externa podem confundir ganho de desenvolvimento com generalização;
- pergunta, contribuições e resumo do resultado negativo;
- deixar explícito que resultados negativos e emendas são parte da contribuição metodológica.

### 6.2 Trabalhos relacionados

- odometria visual, LiDAR e LiDAR-inercial em ambientes naturais;
- fusão de estimadores e filtragem clássica;
- fusão aprendida, modelos temporais causais e máscaras de disponibilidade;
- avaliação de trajetória e riscos de vazamento temporal;
- protocolos cegos, separação por sequência e reprodutibilidade.

As referências devem ser buscadas e verificadas em fontes primárias antes da redação. As referências já existentes no
relato cobrem BotanicGarden, RELLIS-3D, ORB-SLAM3, OpenVSLAM/Stella, KISS-ICP e FAST-LIO2.

### 6.3 Dados e fontes de odometria

- BotanicGarden, plataforma e sensores;
- ORB-SLAM3, Stella VSLAM, FAST-LIO2 e KISS-ICP;
- duas sequências de desenvolvimento e oito externas em três dias;
- alinhamento temporal causal, validade, retenção e indicadores;
- cobertura e continuidade das fontes, sem apresentar RELLIS-3D como teste de erro.

### 6.4 Modelos

- B5/T1: média das fontes válidas e política causal;
- T2: filtro de Kalman de velocidade;
- STEP: ponderação por passo;
- MLP-W: janela causal explícita;
- CNN-W: convolução causal selecionada entre CNN e LSTM;
- pós-filtro comum `alpha = 1,0`, janela `W = 5` e consequências dessa escolha;
- normalização, máscaras, sementes e orçamentos congelados.

### 6.5 Delineamento experimental

- LOSO nas duas sequências de desenvolvimento;
- seleção sequencial de `alpha`, `W`, configurações e T2;
- gate que invalidou a hipótese original;
- emenda H1', com origem pós-desenvolvimento declarada;
- treinamento final em desenvolvimento apenas;
- job cego, manifestos, auditoria e abertura única;
- unidade de análise por sequência e condição adicional por dia;
- RMSE linear/angular como primárias; RPE de 10 m e ATE como trajetória.

### 6.6 Resultados

1. Reprodutibilidade do piloto e seleção dos modelos.
2. Falha da hipótese original no gate.
3. Resultado externo da H1' por sequência e por dia.
4. Custos no RMSE linear e no RPE de 10 m.
5. Comparações descritivas de STEP, MLP-W e T2.
6. Dispersão entre sementes e contraste desenvolvimento versus teste.

### 6.7 Discussão

- o padrão angular aprendido nas duas sequências conhecidas não transferiu para outros dias;
- a média simples é um baseline forte e difícil de superar sem degradar trajetória;
- T2 sugere que estrutura e calibração de incerteza podem transferir melhor neste conjunto, mas essa interpretação
  precisa de teste independente;
- cinco sementes medem variabilidade do treinamento, não variabilidade das fontes;
- consequência metodológica: selecionar só por desenvolvimento teria produzido uma conclusão otimista.

### 6.8 Ameaças à validade

- somente duas sequências de desenvolvimento;
- oito sequências externas agrupadas em três dias, no mesmo local e plataforma;
- uma realização oficial de cada VO por sequência externa;
- H1' formulada depois dos resultados de desenvolvimento, embora antes do teste externo;
- ausência de margem independente de relevância prática para as guardas;
- código do analisador secundário registrado depois da abertura, ainda que implemente regras já congeladas;
- nenhuma inferência sobre outros datasets, sensores ou implantação no robô real.

### 6.9 Conclusão

- responder H1' diretamente;
- separar conclusão confirmatória de observações descritivas;
- destacar o valor do protocolo cego e do resultado negativo;
- propor teste futuro independente para T2 e para modelos que tratem translação e rotação separadamente.

## 7. Figuras propostas

| Figura | Conteúdo | Evidência de origem |
|---|---|---|
| 1 | Fluxo desenvolvimento → congelamento → job cego → abertura única | plano, emendas e manifestos |
| 2 | `Delta` angular da CNN por sequência, agrupado por dia, com linha em zero | `h1_prime_by_sequence.csv` |
| 3 | Contraste entre ganho angular no desenvolvimento e efeito externo | gate e resultado G1 |
| 4 | RMSE angular, linear e RPE de 10 m dos cinco modelos por sequência | `per_sequence_metrics.csv` |
| 5 | Diagrama de disponibilidade das quatro fontes e máscaras causais | tabelas cegas e manifesto de features |

A Figura 2 deve ser a visualização principal: ela mostra imediatamente que sete das oito sequências ficaram abaixo de
zero e que nenhum dia teve mediana favorável. Barras isoladas não devem sugerir independência estatística entre
sequências do mesmo dia.

## 8. Tabelas propostas

| Tabela | Conteúdo |
|---|---|
| 1 | Divisão de dados, dias, duração/linhas e papel de cada sequência |
| 2 | Configurações, parâmetros, sementes e orçamento dos modelos congelados |
| 3 | Gate de desenvolvimento e motivo da inviabilidade da hipótese original |
| 4 | H1' por sequência, medianas por dia e decisão |
| 5 | Comparação externa agregada: angular, linear e RPE de 10 m |
| 6 | Cobertura, falhas e continuidade das quatro fontes |
| apêndice | Métricas por semente, RPE rotacional, ATE, hashes e ambiente |

## 9. Vocabulário de conclusão

Formulações permitidas:

- “A H1' foi negativa sob a regra pré-registrada.”
- “O ganho angular de desenvolvimento não se generalizou às oito sequências externas.”
- “T2 apresentou menor RMSE angular que B5 nas oito sequências, em análise descritiva.”
- “Os resultados sustentam generalização apenas para outras sequências/dias no mesmo ambiente e plataforma.”

Formulações que os dados não permitem:

- “O Kalman é o melhor modelo.”
- “Redes temporais não funcionam para fusão de odometria.”
- “T2 superou confirmatoriamente as redes.”
- “As oito sequências são oito amostras independentes.”
- “A CNN não degradou a translação ou a trajetória.”

## 10. Mapa de evidências

| Afirmação | Fonte versionada | Artefato local |
|---|---|---|
| Seleção de `alpha`, `W` e modelos | `docs/RESULTS_phase3_pilot.md` | `formal_phase3/*.json` |
| Inviabilidade da H1 original e definição da H1' | `docs/amendment_phase4_hypothesis.md` | `gate_dev_rmse.json` |
| Pesos e configurações congelados | `configs/model_comparison_frozen.json` | `final_models/` |
| Integridade do job cego | `docs/RESULTS_phase4_external.md` | manifestos de features/predições |
| Decisão H1' e guardas | `docs/RESULTS_phase4_external.md` | `external_results/*.csv` |
| História acadêmica completa | `docs/RELATO_ACADEMICO_PIPELINE.md` | relatórios e logs citados |

## 11. Próximas entregas para transformar o roteiro em manuscrito

1. Gerar as Figuras 1–4 diretamente dos artefatos com hash, com script versionado e sem nova seleção analítica.
2. Montar as Tabelas 1–6 em formato compacto de artigo.
3. Redigir Introdução e Trabalhos Relacionados usando apenas referências primárias verificadas.
4. Converter as seções de método e resultados deste roteiro em texto corrido no formato do veículo escolhido.
5. Revisar com o orientador o enquadramento: artigo de método/benchmark com resultado negativo, sem promover T2 a
   hipótese posterior.
6. Escolher veículo, idioma e limite de páginas; só então adaptar título, resumo e extensão dos apêndices.
