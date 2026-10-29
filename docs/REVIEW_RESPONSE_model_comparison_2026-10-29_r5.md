# Resposta ao quinto parecer — comparação de modelos

**Data:** 29/10/2026

**Documentos revisados:** `docs/PLAN_model_comparison.md` e `docs/INVENTORY_G0.md`

**Estado:** estrutura aprovada; inventário catalográfico G0 iniciado sem abertura de dados externos.

## 1. Validação das correções anteriores

Fica registrado o aceite de `E_antes = max(E_gt, R + M_α)`, `E_depois = max(E_gt, R)`, da inicialização de Pα na
primeira predição válida, da exclusão de `α = 0`, do teste de prefixo e do transporte de `optimizer.step()` como regra
de orçamento, não como equivalência entre tamanhos de treino.

Nenhuma mudança nessas decisões foi necessária.

## 2. Viabilidade estrutural de α

A sugestão foi incorporada como requisito do protocolo: antes das grades, serão fixados um `α_min` e uma fração máxima
da subdobra que pode ser consumida pelos embargos. Um candidato que ultrapasse esse limite será estruturalmente
inviável, independentemente de sua perda. Os valores numéricos permanecem pendentes para o protocolo e não poderão ser
escolhidos depois de observar métricas da grade.

## 3. Início de G0

O catálogo oficial possui oito candidatas públicas ainda não usadas com links de VLIO e GT. Esse achado resolve apenas
a existência catalográfica. Os bags não estão locais e não foram baixados ou abertos; por isso, a elegibilidade e o
valor final de `k` continuam pendentes de triagem estrutural cega. Critérios, candidatos e limites da alegação foram
registrados em `docs/INVENTORY_G0.md`.

Nenhum modelo foi executado, nenhuma odometria foi processada e nenhum valor de GT ou erro foi consultado.
