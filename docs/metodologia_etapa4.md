# Metodologia — Etapa 4: diagnóstico territorial e seções prioritárias

- **Scripts:** `13_diagnostico.py` (executa `sql/13` e `sql/14` e gera gráficos exploratórios), `14_testes_etapa4.py`, `15_exportar_etapa4.py`.
- **Reprodução:** `powershell -ExecutionPolicy Bypass -File scripts\executar_etapa4.ps1` (≈ 30 s).
- **Entradas (não alteradas):** `analise.indicadores_seccion_oferta` e `analise.oferta_seccion_periodo` (Etapa 3),
  `analise.resultado_origem` e `analise.parcelas_demanda` (Etapa 2).

## Variáveis

| Variável | Definição |
|---|---|
| Densidade (principal) | população INE 01/01/2024 ÷ área total da seção (km², EPSG:25830) |
| Densidade de área habitada (complementar) | população INE ÷ área de células IECA habitadas fora de água, parques e ferrovia. Não substitui a principal; em média é 1,34 × maior |
| Cobertura física | % da população estimada pela grade com parada com serviço a ≤ 400 m de percurso (Etapa 2) |
| Diversidade de linhas | média de linhas acessíveis no período, ponderada pela população **coberta** |
| Frequência | média de partidas/h acessíveis no período, ponderada pela população **coberta** |
| Moradores sem oferta acessível | sem parada a 400 m, ou com parada mas sem partida no período |

As médias de linhas e de frequência entre cobertos separam pouca oferta de ausência física de paradas. As médias que
incluem os não cobertos como zero (Etapa 3) também são mantidas e usadas no ranking.

## Limiares (cenário principal; manhã 07–09)

Os critérios são comparativos internos a Sevilla, não padrões técnicos ou legais. Os percentis usam `percentile_cont`
(interpolação linear), e empates no limiar entram na categoria.

| Critério | Regra | Limiar efetivo | Seções (todas) | Seções de alta densidade |
|---|---|---|---|---|
| Alta densidade | ≥ P75 das 521 seções | **30.976,8 hab./km²** | 131 | — |
| Baixa cobertura | cobertura < cobertura municipal | **< 94,36%** | 72 | 5 |
| Baixa diversidade | ≤ P25 das 519 seções com cobertos | **≤ 2,04 linhas** | 130 | 23 |
| Baixa frequência | ≤ P25 idem | **≤ 15,21 partidas/h** | 130 | 23 |

**Cobertura:** o quartil inferior da cobertura é 100%, porque 426 seções têm cobertura total, e não discrimina nada.
Por isso a regra objetiva é ficar abaixo da média municipal, um parâmetro fixado antes de olhar seções específicas.
Duas seções sem população coberta (cobertura de 0%) não recebem os critérios de diversidade e frequência, pois a
deficiência delas é de acesso. Nenhuma seção tem mais de 10% de população com acessibilidade não determinada (máximo de
2,9%), então nenhuma foi marcada como `informacao_incompleta`.

## Tipologia (seções de alta densidade) — `analise.diag_classificacao`

Precedência:

| Ordem | Condição | Categoria |
|---|---|---|
| 1 | Não é de alta densidade | `fora_alta_densidade` (as flags continuam registradas) |
| 2 | ≥ 2 deficiências | **D** combinadas |
| 3 | Só baixa cobertura | **A** |
| 4 | Só baixa diversidade de linhas | **B** |
| 5 | Só baixa frequência | **C** |
| 6 | Nenhuma | `alta_densidade_sem_deficiencia` |

Cada seção guarda as três flags, a lista (`deficiencias`), o número delas e as dimensões: acesso (cobertura) e serviço
(linhas e/ou frequência). **Prioritária** = alta densidade e ao menos uma deficiência.

| Categoria | Seções | Pop. INE | % de Sevilla |
|---|---|---|---|
| A baixa cobertura | 5 | 6.627 | 1,0% |
| B poucas linhas | 5 | 6.974 | 1,0% |
| C baixa frequência | 5 | 6.011 | 0,9% |
| D combinadas (todas: linhas + frequência) | 18 | 21.596 | 3,1% |
| **Prioritárias (A–D)** | **33** | **41.208** | **6,0%** |
| Alta densidade sem deficiência | 98 | 122.666 | 17,9% |
| Fora da alta densidade | 390 | 522.867 | 76,1% |

Nenhuma seção densa combina deficiência de acesso com deficiência de serviço. Linhas e frequência quase sempre aparecem
juntas: a correlação entre seções é de 0,95, e 18 das 23 seções densas com poucas linhas também têm baixa frequência.

## Ranking — `ranking` em `analise.diag_classificacao`

Ordem lexicográfica, sem escore:
1. mais **dimensões** deficientes (acesso, serviço);
2. mais moradores sem oferta acessível na manhã;
3. menor média de partidas/h (todos os moradores determinados);
4. menor média de linhas;
5. maior densidade;
6. `cusec`.

**Ajuste em relação à ordem inicial:** o critério 1 inicial era o número de deficiências (1–3). Como linhas e frequência
medem quase a mesma dimensão, contá-las separadamente punha à frente seções com cobertura total e uma linha. Ficavam atrás,
por exemplo, uma seção com 87% dos moradores sem parada (4109106003, 907 hab.). A ordem inicial foi preservada em
`ranking_ordem_inicial`, para comparação.

O primeiro lugar é o mais prioritário segundo esses critérios, e não necessariamente onde uma intervenção renderia mais.

**Top 10:**

| # | Seção | Distrito | Tipo | Pop. INE | Densidade | Situação |
|---|---|---|---|---|---|---|
| 1 | 4109106003 | 06 | A | 1.131 | 39.320 | 907 hab. estimados sem parada (cobertura 12,9%) |
| 2 | 4109111012 | 11 | A | 2.034 | 40.363 | 346 sem parada (76,4%) |
| 3 | 4109111014 | 11 | A | 1.239 | 43.250 | 105 sem parada (87,7%) |
| 4 | 4109109047 | 09 | A | 1.015 | 34.348 | 91 sem parada (86,4%) |
| 5 | 4109111011 | 11 | A | 1.208 | 37.257 | 53 sem parada (93,3%) |
| 6 | 4109104054 | 04 | D | 1.093 | 33.592 | 1,5 linha, 7,1 partidas/h (41 sem parada) |
| 7 | 4109106036 | 06 | D | 883 | 38.490 | 1 linha, 4,6 partidas/h |
| 8 | 4109107005 | 07 | D | 1.511 | 36.590 | 1 linha, 5,5 partidas/h |
| 9 | 4109102058 | 02 | D | 1.109 | 38.732 | 1,05 linha, 6,4 partidas/h |
| 10 | 4109105034 | 05 | D | 1.982 | 34.783 | 1,5 linha, 8,2 partidas/h |

## Períodos — `analise.diag_temporal`

- **Indicadores por seção:** partidas/h nos três períodos, diferenças tarde − manhã e entrepico − manhã, variação % (nula
  quando a manhã é 0, o que ocorre em 5 seções), posição relativa (`percent_rank`) e sua mudança. Baixa frequência é
  avaliada em cada período, com o P25 de cada um (manhã 15,21; entrepico 15,50; tarde 12,90 partidas/h).
- **Redução à tarde:** confirmada em 475 seções. A variação mediana é de −14,4%; 72 seções perdem ≥ 25%. Na posição
  relativa, 17 caem ≥ 10 pontos percentuais da distribuição e 5 sobem ≥ 10.
- **Padrão de baixa frequência:**

  | Padrão | Seções | Prioritárias |
  |---|---|---|
  | Persistente (nos três períodos) | 117 | 22 |
  | Parcial | 17 | — |
  | Baixa sobretudo à tarde | 11 | 2 de alta densidade, nenhuma prioritária |

  A baixa frequência das áreas prioritárias é estrutural, não restrita à tarde. Diferenças de frequência entre
  períodos refletem a programação, não a demanda.

## Densidade × oferta — `analise.diag_densidade_relacao` e `diag_densidade_quartis`

| Densidade × indicador | Pearson | Spearman |
|---|---|---|
| cobertura 400 m | 0,23 | 0,37 |
| linhas (manhã) | 0,13 | 0,21 |
| partidas/h (manhã) | 0,16 | 0,22 |
| partidas/h (tarde) | 0,14 | 0,19 |
| população sem cobertura (absoluta) | −0,30 | −0,43 |

| Quartil de densidade | Cobertura | Partidas/h (manhã) | Sem cobertura |
|---|---|---|---|
| Q1 | 89,2% | 24,5 | 24.169 hab. |
| Q4 | 98,8% | 34,9 | 1.542 hab. |

Spearman calculado com posto médio nos empates (correção da Etapa 5: a versão inicial usava `rank()`, o que subestimava
a correlação com a cobertura — 0,23 em vez de 0,37 — por causa das 426 seções com 100%; os demais valores mudaram
menos de 0,005). A oferta cresce pouco com a densidade. Os moradores sem parada concentram-se nas seções menos densas, mas há
seções densas com oferta mínima: 23 das 131 seções de alta densidade estão no quartil inferior de frequência.
Correlação não implica causalidade.

Gráficos exploratórios: `resultados/etapa4/graficos/` (densidade × cobertura, linhas, partidas/h e população sem
cobertura; manhã × tarde).

## Seções citadas na Etapa 3 (verificadas pelos critérios, sem inclusão manual)

| Seção | Densidade | Situação | Classificação |
|---|---|---|---|
| 4109106003 | 39.320 | 12,9% coberta | **prioritária nº 1 (A)**. Com tercis vira D |
| 4109101028 | 23.068 | coberta só pela C5, que não opera pela manhã; 2 partidas/h no entrepico | linhas + frequência deficientes, mas abaixo de P75 (e de P66,7) → `fora_alta_densidade` |
| 4109101033 | 22.828 | idem | idem |
| 4109106007 | 24.632 | as três deficiências | abaixo dos dois limiares de densidade → não prioritária |

As seções 4109101028, 4109101033 e 4109106007 mostram que o recorte por densidade deixa de fora áreas com deficiência
severa e densidade intermediária. Elas continuam identificáveis pelas flags na tabela consolidada.

## Conferência das prioritárias — `analise.diag_conferencia_prioritarias` (15 primeiras)

- **Tamanho:** são seções pequenas e compactas (0,023–0,057 km²), inteiramente residenciais, sem barreiras OSM
  (rio, ferrovia, autovia) atravessando a seção.
- **Paradas:** têm 2–9 paradas a 400 m, com 1–5 linhas.
- **Percurso:** a razão rede/linha reta até a parada mais próxima fica entre 1,3 e 2,8 (desvios de quarteirão).
- **Grade:** a razão grade/INE é de 0,59–0,97. A grade subestima a população dessas seções pequenas e densas, porque
  parte das células é atribuída às vizinhas. Isso não altera os percentuais, mas reduz os números absolutos de afetados.
- **Sensibilidade ao limiar de 400 m:** em 3 prioritárias, mais de 50% da população estimada está a 350–450 m da parada
  mais próxima. São as nº 1 (4109106003, 95%), nº 3 (4109111014, 100%) e 4109109047 (42%). A nº 1 depende de um único
  ponto de demanda com 907 hab., a 444 m de percurso (294 m em linha reta) de uma parada de Esperanza de Triana.
  A classificação é correta pela regra, mas próxima do limiar. Indicador: `pct_pob_perto_limiar_400m`.

## Sensibilidade — tercis (P66,7 / P33,3; baixa cobertura < 99%)

- **Seções:** 58 prioritárias com tercis, contra 33 com quartis. **As 33 permanecem nos dois cenários** e as 25 novas
  são acréscimos: 2 A, 4 B, 7 C e 12 D.
- **Ranking:** o top 10 dos quartis está inteiro no top 20 dos tercis, e a correlação de Spearman dos postos comuns é 0,997.
- **Distritos:** 9 com prioritárias nos dois cenários (01 e 10 não têm nenhuma). O distrito 04 concentra o maior
  número com tercis (17).
- **Conclusão:** as conclusões territoriais não dependem do limiar. O que muda é o tamanho do universo prioritário.

## Distritos (exploratório; códigos INE) — `analise.diag_sintese_distrito`

| Distrito | Prioritárias | Tipos | Pop. em prioritárias | Observação |
|---|---|---|---|---|
| 04 | 7 | — | 20,8% da pop. prioritária | média baixa de partidas/h: 18,8 (manhã) |
| 06 | 5 | 1 A + 4 D | 12,8% | inclui a nº 1 |
| 07 | 4 | — | 12,6% | — |
| 09 | 4 | — | 13,6% | — |
| 11 | 4 | 3 A | 13,9% | 22,5% da população do distrito em seções prioritárias |
| 02, 08 | 3 cada | — | — | — |
| 05 | 2 | — | — | — |
| 03 | 1 | — | — | — |
| 01, 10 | 0 | — | — | sem seções prioritárias |

## Tabelas e views criadas no schema `analise`

**Tabelas:** `diag_base`, `diag_limiares`, `diag_classificacao` (2 cenários), `diag_temporal`, **`diag_resultado_seccion`**
(consulta direta por seção), `diag_sintese_tipologia`, `diag_sintese_municipal`, `diag_sintese_distrito`,
`diag_densidade_relacao`, `diag_densidade_quartis`, `diag_sensibilidade`, `diag_sensibilidade_resumo`,
`diag_conferencia_prioritarias`.

**Views:** `v_diag_secoes`, `v_diag_prioritarias`, `v_diag_distritos` e `v_diag_paradas`, todas em EPSG:25830.

## Exportações — `resultados/etapa4/` (precisão completa)

**CSV:** indicadores completos (521), prioritárias, ranking, limiares, sínteses municipal, por tipologia e por distrito,
comparação de períodos, sensibilidade (por seção e resumo), relação com a densidade, quartis e conferência.

**GeoPackages:**
- `etapa4_secoes_classificadas.gpkg` (seções, prioritárias, distritos);
- `etapa4_apoio_interpretacao.gpkg` (paradas de ônibus com linhas e partidas/h, pontos de demanda da manhã, limite
  municipal, barreiras OSM).

As camadas TUSSAM da IDE Sevilla não são incluídas, por causa da restrição de redistribuição.

## Limitações

- **Limiares relativos:** são internos à cidade. O "baixo" de Sevilla pode ser adequado em outra referência, e vice-versa.
- **Densidade por área total:** subestima a densidade de seções com áreas não residenciais. Pela densidade de área
  habitada, 13 seções adicionais ultrapassariam o limiar; elas não foram reclassificadas.
- **Recorte por densidade:** exclui seções com deficiência severa e densidade intermediária (ex.: 4109106007).
- **Números absolutos:** os afetados vêm da grade, que subestima as seções pequenas e densas (razão grade/INE < 1 no top 15).
- **Coberturas binárias:** o limite de 400 m é rígido; há seções sensíveis a ele (ver conferência).
- **Herdadas:** oferta programada (não realizada), 77% de horários interpolados com baixa sensibilidade, rede OSM e
  representação da demanda por pontos.
