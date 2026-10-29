# Resposta ao sexto parecer — inventário G0

**Data:** 29/10/2026

**Documentos revisados:** `docs/INVENTORY_G0.md` e `docs/PLAN_model_comparison.md`

**Estado:** quatro pendências pré-download incorporadas; nenhum bag ou GT externo aberto.

## 1. Dependência entre sequências do mesmo dia

O agrupamento `1005` (quatro sequências), `1006` (duas) e `1008` (duas) foi acrescentado. A sequência permanece como
unidade da regra principal, mas a condição confirmatória também exigirá efeito mediano favorável em cada dia, para cada
contraste e métrica primária. Os três dias precisam estar representados depois da triagem.

Essa condição não torna as sequências independentes nem permite inferência robusta com apenas três clusters. A
dependência intradia foi registrada como limitação, e os valores exatos do teste de sinais para `k = 8` foram
documentados apenas como referência.

## 2. Limite da alegação

“Percursos não vistos” foi substituído por “novas sequências, de outras datas, no mesmo local e na mesma plataforma”.
Sobreposição de rotas não será inferida sem abrir poses ou figuras de trajetória.

## 3. Permanência após a triagem

Uma sequência aprovada estruturalmente não poderá ser excluída porque uma VO não inicializou, um método falhou ou a
cobertura ficou baixa ou nula. Esses eventos serão resultados do teste. Nova execução só será admitida para falhas
externas ao método e pré-enumeradas; falha do método, baixa validade e desempenho ruim não autorizam repetição.

## 4. Equivalência do GT

A triagem exigirá a mesma proveniência nominal do GT do desenvolvimento — mapa de levantamento do BotanicGarden com
scanner Leica —, frame VLP-16 e esquema canônico de timestamp, posição e quaternion. Foram criados códigos distintos
para incompatibilidade de proveniência e formato.

Os critérios e códigos foram fixados antes da implementação de G1 e antes de qualquer aquisição.
