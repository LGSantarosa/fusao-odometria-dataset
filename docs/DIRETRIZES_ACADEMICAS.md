# Diretrizes para registro acadêmico dos experimentos

Estas diretrizes foram extraídas dos documentos de qualificação localizados na raiz de
`/home/rbe-luis/Workspace` e devem ser aplicadas a toda evidência produzida neste projeto.

## 1. Dois níveis de documentação

Os registros operacionais e o texto acadêmico têm funções diferentes e devem coexistir:

- **registro operacional:** comandos, versões, caminhos, logs, falhas, tentativas e estado do processamento;
- **registro acadêmico:** problema investigado, hipótese, método, resultados, interpretação, limitações e relação com
  as questões de pesquisa.

Um resultado não deve ser levado à dissertação apenas a partir do log operacional. Após sua validação, ele deve ser
incorporado a `docs/RELATO_ACADEMICO_PIPELINE.md` em linguagem acadêmica.

## 2. Estrutura mínima de cada experimento

Cada experimento concluído deve registrar:

1. **Objetivo:** qual pergunta o experimento procura responder.
2. **Hipótese ou expectativa:** qual comportamento era esperado e por quê.
3. **Dados e configuração:** dataset, sequência, intervalo, sensores, calibração, versões, parâmetros e repetições.
4. **Procedimento:** etapas executadas e critérios definidos antes da análise.
5. **Métricas:** unidades, denominadores, cobertura e condições de elegibilidade.
6. **Resultados:** valores observados, incluindo resultados negativos e execuções malsucedidas relevantes.
7. **Discussão:** interpretação sustentada pelos dados e comparação com as hipóteses.
8. **Ameaças à validade:** explicações alternativas, vieses, limitações e alcance da conclusão.
9. **Decisão decorrente:** mudança de configuração, correção, novo experimento ou manutenção da hipótese em aberto.
10. **Rastreabilidade:** caminhos dos artefatos, commit, configuração e documento técnico que contém a evidência bruta.

## 3. Regras de escrita e inferência

- Empregar português formal, frases completas e termos definidos antes do uso.
- Distinguir observação, interpretação, hipótese e conclusão.
- Não apresentar correlação como causalidade sem experimento controlado.
- Não transformar ausência de evidência em evidência de ausência.
- Informar quando um resultado não possui GT ou quando o GT tem qualidade limitada.
- Apresentar erro junto com cobertura e continuidade; uma métrica isolada não representa robustez.
- Explicitar diferenças entre modalidades, especialmente o uso de IMU pelo FAST-LIO2.
- Usar tempo passado para procedimentos concluídos e futuro apenas para atividades ainda não executadas.
- Não incorporar resultados de processos em andamento ou arquivos ainda não validados.
- Manter unidades no Sistema Internacional e definir siglas na primeira ocorrência.
- Identificar tabelas e figuras com título e fonte, preferencialmente “Fonte: Elaborada pelo autor (ano)” quando forem
  produzidas neste trabalho.
- Utilizar referências primárias para datasets, algoritmos e métricas; não inventar dados bibliográficos.

## 4. Relação com a dissertação

O texto deve apoiar a estrutura da qualificação:

- **Introdução:** contexto, motivação, questões de pesquisa, objetivos, hipóteses e ameaças à validade;
- **Fundamentação:** conceitos necessários para compreender sensores, odometrias, frames, sincronização e métricas;
- **Trabalhos relacionados:** posicionamento dos métodos e da contribuição perante a literatura;
- **Metodologia:** datasets, algoritmos, pipeline, indicadores, modelo de dados e validação;
- **Resultados:** configuração experimental, valores observados, comparação e discussão;
- **Conclusão:** resposta às questões de pesquisa, contribuições, limitações e trabalhos futuros.

O pipeline deste repositório pertence principalmente à Metodologia e aos Resultados. Sua contribuição é fornecer um
dataset derivado causal, reproduzível e livre de vazamento de GT para o treinamento e a avaliação do modelo adaptativo.

## 5. Checklist antes de consolidar um resultado

- [ ] O processo terminou sem tarefas ou nós órfãos.
- [ ] Os arquivos de saída passaram pelo teste de contrato.
- [ ] A configuração e a versão do método foram registradas.
- [ ] O denominador das porcentagens está explícito.
- [ ] A cobertura e as falhas são apresentadas junto com ATE/RPE.
- [ ] Repetições e variabilidade foram informadas quando aplicáveis.
- [ ] A conclusão não ultrapassa a evidência disponível.
- [ ] As ameaças à validade foram atualizadas.
- [ ] O resultado foi incorporado ao relato acadêmico.
- [ ] O caminho da evidência bruta e o commit foram registrados.
