# Metodologia — Etapa 2: acesso caminhável às paradas TUSSAM em até 400 m

Scripts: `06_barreiras_osm.py` → `07_acessibilidade.py` (executa `sql/05`–`08` e `rede_acessibilidade.py`) →
`08_testes_etapa2.py` → `09_exportar_etapa2.py`. Parâmetros em `config/config.yaml` (`acessibilidade:`), que
também são gravados em `analise.parametros`. Um único comando reconstrói a etapa:
`powershell -ExecutionPolicy Bypass -File scripts\executar_etapa2.ps1` (cerca de 1 min, além dos testes).

## 1. Abrangência da grade IECA

- As 887 células cobrem 55,49 km² (sem sobreposição: a área da união é igual), contra 141,45 km² das seções.
  **A camada publica apenas células habitadas.** Isso foi verificado de três formas:
  - no WFS não existe nenhuma célula com `pob_tot ≤ 0` em toda a Andaluzia (61.234 células);
  - o filtro `cmun LIKE '%41091%'` devolve exatamente as 887 células carregadas;
  - a menor célula tem 2 habitantes (o valor convencional de sigilo).
  A memória técnica também descreve a grade como a agregação da população geocodificada por portal.
  Nenhum erro de aquisição ou filtragem foi encontrado, e nada foi corrigido.
- As áreas sem células são compatíveis com espaços sem residentes, como o rio, a Dársena, parques, áreas
  portuárias e industriais, o aeroporto e o solo rústico.
- Todas as 521 seções têm ao menos um ponto de demanda.
- **Grade × INE por seção:** a razão entre a população estimada pela grade e a do INE varia de 0,26 a 3,22. Em 152 seções
  ela fica entre 0,9 e 1,1. A causa é a ponderação por área de células de 250 m sobre seções pequenas: a grade não
  segue os limites das seções. No total municipal, a diferença é −0,36% (684.251 × 686.741). Por isso, os
  percentuais por seção usam como denominador a população da grade, e `pob_ine` fica como referência separada.
  Nenhum valor foi ajustado para forçar igualdade.

## 2. Distribuição da população das células (`analise.parcelas_demanda`)

- **Parcela** = célula ∩ seção (EPSG:25830). São 2.685 parcelas, 703 delas em células divididas entre várias seções.
  Parcelas com menos de 1% da área da célula são fundidas às demais da mesma célula, salvo quando são a maior parcela.
- **Área habitável** = área da célula fora de água, parques, terrenos ferroviários (OSM) e de uma faixa de 10 m ao longo de
  ferrovias e vias expressas em nível. Isso evita que residentes sejam atribuídos ao leito do rio ou a pátios ferroviários.
- **Regra** (`pob_estimada = pob_tot × cota_municipio × peso_parcela`):
  - `cota_municipio` = 1 para as 850 células só de Sevilla. Nas 37 multimunicipais (`cmun` = `41038 / 41091` etc.),
    é a fração da área habitável dentro do limite INE. A parte dos vizinhos não é atribuída a Sevilla.
  - `peso_parcela` = área habitável da parcela ÷ área habitável das parcelas mantidas da célula. Os pesos somam 1 por
    célula, e nenhuma célula é atribuída integralmente a mais de uma seção.
  - Células sem área habitável usam a área total (apenas 1 caso).
- **Conservação:** as células exclusivas somam exatamente 679.148, que é o total publicado. As multimunicipais contribuem
  com 5.103,2, e o total estimado é **684.251,15**. Com a área total, o resultado seria 684.156,5; a troca para área
  habitável realoca 32.617 hab. entre parcelas.
- **Sigilo:** as 59 células com valor convencional 2 entram com esse valor, sinalizadas (`sigilo_total_convencional`).
  Elas somam **109,9 hab.** e não são contagens exatas. Não foram excluídas nem relocadas.

## 3. Pontos de demanda (`analise.pontos_demanda`)

- **2.674 pontos**, um por parcela com população > 0. O ponto é o centroide da área habitável da parcela, ou
  `ST_PointOnSurface` quando o centroide cai fora dela (113 casos).
- Em 1.154 pontos o resultado difere do centroide geométrico da parcela (deslocamento máximo de 192 m).
  Cada ponto guarda: id da célula (`gidmp`, `grd_fixid`), `cusec`, população, peso, cota, sinal de sigilo, regra aplicada e coordenadas.
- O ponto é uma localização representativa, não residencial.

## 4. Paradas de destino (`analise.paradas_analise`)

| Categoria | Paradas |
|---|---|
| Ônibus com serviço em 21/10/2026 (destinos) | 1.027 |
| Ônibus sem serviço no dia | 16 |
| Somente bonde T1 (excluídas) | 12 |

Coordenadas e IDs do GTFS foram mantidos sem alteração. As divergências com a camada IDE ficam registradas em `situacao_ide`
(3 com mesmo ID e posição distante, 6 só no GTFS) e listadas em `analise.excecoes`.

## 5. Rede utilizável e ligações

**Rede** (`analise.rede_arestas`; nenhuma aresta foi apagada, cada uma tem `motivo_exclusao`):

| Motivo | Arestas |
|---|---|
| `via_expressa_sem_passagem_pedonal`: trunk/motorway (autovías A-376, A-92, SE-20…) sem `foot` ou `sidewalk` | 364 |
| `acesso_proibido`: `access=no/private` sem permissão a pedestres (inclui as baias de ônibus `service`) | 246 |
| `via_exclusiva_onibus`: `busway` | 27 |
| `atravessa_agua_sem_ponte`: trilha informal que divide o polígono do rio sem `bridge` | 4 |

O resultado são 46.802 arestas utilizáveis e 258 componentes. O principal tem 30.300 nós. Os componentes isolados
são preservados e **não são conectados entre si**.

**Barreiras** (`analise.barreiras`, OSM): polígonos de água e rios/canais lineares, ferrovias e vias expressas em nível.
Pontes e túneis não bloqueiam.

**Ligação ponto → rede** (`analise.ligacoes_origem`, `analise.ligacoes_parada`):
1. Candidatas: as 30 arestas utilizáveis mais próximas dentro do raio (250 m para origens, 50 m para paradas).
2. A ligação, o segmento mais curto até a aresta, **não pode atravessar barreira**. Para polígonos, vale uma interseção
   de mais de 1 m; para linhas, `ST_Crosses`.
3. A ligação primária é a candidata válida mais próxima. Empate: menor `aresta_id`.
4. Se a primária cair em componente isolado, acrescenta-se a candidata válida mais próxima do componente principal,
   até 250 m para origens e 50 m para paradas. Isso aconteceu em 24 origens e 2 paradas.

As ligações são de mão única e ficam fora do grafo: são somadas ao início e ao fim do percurso. Assim, nenhuma origem
ou parada serve de passagem entre componentes.

**Paradas:** todas as 1.027 estão ligadas, com ligação mediana de 5,2 m e máxima de 36,5 m. As 5 paradas que estavam
a 103–228 m do nó mais próximo (Ctra. Pino Montano, Av. La Prensa, Villanueva del Pítamo) ficam a ≤ 37 m da
**aresta**: a distância anterior era só o efeito de arestas longas. Das 12 paradas com nó mais próximo fora do componente
principal, apenas 2 continuam fora: 925 Parlamento e 950 Esparteros receberam a ligação secundária ao principal
(18,7 e 8,4 m). Outras 30 paradas estão em baias `service` com `access=no` ou junto a autovías e foram ligadas à via
pedonal mais próxima.
**Exceções:** as paradas 650 e 1002 (Aeropuerto) só alcançam o componente do aeroporto, que só tem ligação viária pela
autovía. Elas ficam marcadas como `ligada_apenas_componente_isolado`. Nenhuma origem está a menos de 400 m delas.

## 6. Cálculo das distâncias (`rede_acessibilidade.py`)

- O grafo é não direcionado (NetworkX). Cada aresta utilizável é dividida nos pontos onde as ligações a tocam, com pesos
  = fração do comprimento real (`ST_Length` em EPSG:25830). O grafo resultante tem 35.273 nós e 49.789 arestas.
  As geometrias de 47.203 arestas estão no sentido v→u e foram tratadas via `no_inicio_geom`.
- Para cada ligação de parada, roda-se um **Dijkstra limitado** (`single_source_dijkstra_path_length`, `cutoff = 400 − ligação`).
  Distância = ligação da parada + rede + ligação da origem ≤ 400 m (tolerância de 0,001 m).
  Para cada par origem–parada fica o menor valor; empates são resolvidos por id de ligação.
  Não se calculam rotas completas entre todos os pares. O cálculo leva cerca de 3 s.
- **Parada mais próxima sem limite:** Dijkstra a partir de uma fonte virtual ligada a todas as paradas, com corte em 5 km.
- A distância euclidiana (`dist_euclidiana_parada_mais_proxima_m`) é guardada apenas como referência.

## 7. Classificação (`analise.resultado_origem`)

| Situação | Regra |
|---|---|
| `coberto_400m` | ≥ 1 parada com serviço a ≤ 400 m de percurso |
| `sem_cobertura_400m` | ligada ao componente principal, sem parada a ≤ 400 m e sem parada de ligação incerta a ≤ 400 m em linha reta |
| `nao_determinado` | sem ligação válida em 250 m (6 pontos, 149 hab.), ligada só a componente isolado (8 pontos, 43 hab.) ou com parada incerta próxima (0) |

`confiabilidade` vale `alta` para ligação ≤ 100 m ao componente principal, `media` para ligação de 100–250 m ou
cobertura via componente isolado, e `indeterminada` para os não determinados.
Ter parada próxima **não** implica oferta efetiva de linhas e partidas, que é tema da Etapa 3.

## 8. Tabelas e views do schema `analise`

**Tabelas:**
- parâmetros e rede: `parametros`, `barreiras`, `areas_nao_residenciais`, `rede_arestas`, `rede_componentes`;
- demanda e paradas: `parcelas_demanda`, `pontos_demanda`, `paradas_analise`;
- ligações e percursos: `ligacoes_origem`, `ligacoes_parada`, **`origem_parada_400m`** (todas as paradas alcançáveis por
  origem, PK origem+parada, índice em `stop_id`), `parada_mais_proxima`;
- resultados: `resultado_origem`, `resultado_seccion` (521 seções), `sintese_municipal`, `excecoes`.

**Views para QGIS:** `v_secciones_cobertura`, `v_pontos_demanda`, `v_paradas`, `v_ligacoes`, `v_origem_parada_linhas`
(linha reta, só para visualização) e `v_resumo_distrito`.
A conferência fica em `qa.amostra_percursos`.

**Exportações** (`resultados/etapa2/`): `sintese_municipal.csv`, `indicadores_secoes.csv`, `resumo_distritos.csv`,
`origem_parada_400m.csv`, `pontos_demanda.csv`, `paradas.csv`, `excecoes.csv` e `etapa2_cobertura_preliminar.gpkg`
(seções, pontos, paradas, ligações, exceções).

## 9. Limitações

- **Pontos representativos:** a distância inclui a ligação em linha reta do centroide da área habitável à rua, com mediana
  de 12 m e 10 pontos acima de 150 m. Moradores reais podem estar mais perto ou mais longe que isso.
- **População por seção:** a estimativa da grade por seção é aproximada (ver §1). A grade e o INE são fontes distintas.
- **Rede OSM:** as calçadas não são modeladas de forma explícita. Vias `trunk` com calçada não etiquetada podem ter sido
  excluídas por precaução, o que é conservador para a cobertura. As passagens de nível ferroviárias são as do OSM.
  Restam 31 sobreposições longitudinais de caminhos com polígonos de canais e lagos, sem travessia.
- **Escala:** os comprimentos em UTM 30N são ~0,05% maiores que os geodésicos em Sevilla (≈ 0,2 m em 400 m).
- **Oferta:** o resultado mede acesso físico a paradas com serviço no dia de referência, sem frequência nem linhas.
  Os horários interpolados (Etapa 1) não afetam esta etapa.
