# Prompt para revisão externa do plano de comparação de modelos

Copiar este texto para o Claude junto com os arquivos listados ao final.

---

Você é um revisor cético de um artigo de robótica e aprendizado de máquina. Revise o plano
`docs/PLAN_model_comparison.md`. O projeto constrói um dataset sincronizado com quatro fontes de odometria e já executou
um primeiro experimento confirmatório com MLPs. O novo plano pretende comparar MLP, CNN 1D causal, LSTM e BiLSTM, além
de estudar a contribuição das fontes.

Não reescreva retroativamente o protocolo nem o resultado já executado. Não presuma dados, sensores ou métricas que não
estejam nos documentos. Diferencie obrigatoriamente modelos causais implantáveis de modelos offline que usam futuro.

Avalie, em particular:

1. vazamento temporal em janelas, estados recorrentes, normalização e purga;
2. o confundimento entre acesso a histórico, arquitetura e tipo de cabeça de saída;
3. justiça da comparação em capacidade, orçamento de otimização e hiperparâmetros;
4. suficiência dos dados, independência da unidade estatística e risco de pseudorreplicação;
5. multiplicidade causada por modelos, sementes, fontes e ablações;
6. desenho das ablações com retreino versus perda de fonte sem retreino;
7. adequação das métricas para precisão, robustez e implantação em tempo real;
8. novidade científica, narrativa do artigo e alegações que os dados realmente sustentam;
9. quais partes devem ser removidas para obter o menor experimento publicável e rigoroso;
10. quais decisões precisam ser congeladas antes de abrir um novo conjunto de teste.

Responda no seguinte formato:

1. **Falhas fatais:** problemas que invalidariam a conclusão se não forem corrigidos.
2. **Revisões obrigatórias:** mudanças necessárias antes do pré-registro.
3. **Melhorias opcionais:** extensões úteis, mas não essenciais.
4. **Pergunta e hipótese revisadas:** uma pergunta central e, se cabível, uma hipótese confirmatória testável.
5. **Matriz mínima recomendada:** modelos, cabeças, fontes e ablações que devem permanecer.
6. **Divisão de dados recomendada:** desenvolvimento, validação e teste externo.
7. **Regra de decisão sugerida:** métricas primárias, comparadores e tratamento de multiplicidade.
8. **Veredito:** `pronto para protocolo`, `revisar antes do protocolo` ou `não viável com os dados atuais`, com
   justificativa curta.

Se houver ambiguidade, faça perguntas explícitas em vez de preencher lacunas por suposição. Cite o arquivo e a seção
que motivam cada crítica importante.

Arquivos para contexto:

- `README.md`;
- `docs/PLAN_model_comparison.md`;
- `docs/protocol_fusion_model.md`;
- `docs/RESULTS_fusion_model.md`;
- `docs/DATASHEET.md`;
- `docs/RELATO_ACADEMICO_PIPELINE.md`, especialmente seções 3.8, 4, 5 e 6.

---
