# Metodologia — Etapa 3: linhas acessíveis e frequência programada

Scripts: `10_oferta_programada.py`, que executa `sql/09`–`12`, depois `11_testes_etapa3.py` e `12_exportar_etapa3.py`.
Reprodução: `powershell -ExecutionPolicy Bypass -File scripts\executar_etapa3.ps1` (≈ 1,5 min de cálculo e ≈ 3 min de testes,
que incluem uma segunda execução completa). Não se refazem a aquisição, a interpolação nem o roteamento de 400 m.

## Dados e períodos

- **GTFS:** TUSSAM `20260928`, serviço `INVLAB40`, o único ativo na quarta-feira 21/10/2026. Não há exceções em
  `calendar_dates`. Fuso `Europe/Madrid`, sem mudança de horário nesse dia (a de outono foi em 25/10).
- **Janelas** (`prep.periodos_analise`), sempre [início, fim):

  | Período | Janela |
  |---|---|
  | manhã | 07:00–09:00 |
  | entrepico | 12:00–14:00 |
  | tarde | 17:00–19:00 |

  Uma partida exatamente às 09:00 não pertence à manhã: 107 partidas caem exatamente num início de janela e
  111 exatamente num fim. O maior horário do feed equivale a 02:58 do dia seguinte, então as viagens noturnas do dia
  anterior não chegam às janelas.

## Definições

- **Partida programada:** passagem de uma viagem de ônibus TUSSAM (`route_type 3`) por uma parada **onde é possível
  embarcar**. A última parada de cada viagem é só desembarque e fica excluída. `pickup_type` é vazio em todo o feed,
  o que significa embarque regular. Resultado em `analise.partidas_dia` (143.463 partidas) e `analise.partidas_periodo`.
  Os horários vêm de `prep.gtfs_horarios_dia` (Etapa 1) e preservam `origem_horario` (explícito ou interpolado).
- **Linha distinta:** `route_id`, que equivale a `route_short_name`. C6A/C6B, 38/38A e CJ/CJ1 são linhas distintas no feed.
  Só conta a linha com ≥ 1 partida acessível no período.
- **Linha-sentido:** par (`route_id`, `direction_id`). Todas as viagens têm `direction_id` 0 ou 1.
- **Partida programada acessível:** viagem com partida no período em alguma parada que a origem alcança a ≤ 400 m
  (`analise.origem_parada_400m`).
- **Deduplicação:** cada viagem (`trip_id`) conta **uma vez** por origem e período, mesmo que passe por várias paradas
  acessíveis. O embarque representativo é a parada de menor caminhada; empate: partida mais cedo, depois `stop_id`.
  Tabela de conferência: `analise.origem_viagem_periodo` (423.277 linhas). A deduplicação removeu 230.199 passagens
  brutas: 184.475 viagens eram acessíveis em mais de uma parada.
- **Partidas por hora** = viagens distintas acessíveis ÷ 2 h. Isso não equivale a viagens realizadas nem a acesso a
  qualquer destino.
- **Intervalo programado** (`analise.origem_linha_sentido_periodo`): por linha-sentido, na parada de referência da origem
  (a de menor caminhada que essa linha-sentido serve). Média = (última − primeira) ÷ (n − 1); também se registra o maior
  intervalo. Com uma só partida na janela fica `uma_partida_na_janela`, sem intervalo. Linhas e sentidos nunca se misturam.
  No nível da origem guarda-se apenas o **menor intervalo médio entre as linhas-sentido**, e não um "intervalo combinado".

## Indicadores

- **Por origem e período** (`analise.oferta_origem_periodo`, 2.674 × 3): paradas a 400 m e com partida, linhas no dia
  e no período, linha-sentido, linhas com os dois sentidos, viagens, partidas/h, viagens com horário de embarque
  explícito ou interpolado, passagens brutas (só para conferência) e menor intervalo.
  **Situação da oferta:**

  | Situação | Valores |
  |---|---|
  | `com_servico` | indicadores calculados |
  | `coberto_sem_servico_no_periodo` | zeros, com paradas > 0 |
  | `sem_cobertura_400m` | zeros |
  | `nao_determinado` | **nulos**: a ausência de serviço não foi comprovada |

- **Por seção e período** (`analise.oferta_seccion_periodo`, 521 × 3):
  - médias ponderadas pela população da grade entre os moradores com acessibilidade determinada (sem cobertura entra como 0);
  - as mesmas médias apenas entre os cobertos;
  - populações e percentuais por situação, com a população do INE mantida separada;
  - % da população com linha no dia, % com linhas nos dois sentidos e % de embarques com horário interpolado.

  As médias descrevem o **morador médio estimado**, não os ônibus que cruzam a seção. Partidas não são somadas entre origens.
- **Tabela larga para a Etapa 4** (`analise.indicadores_seccion_oferta`): densidade, cobertura 400 m, linhas, partidas/h e
  linha-sentido por período, mínimo entre períodos, diferenças entre períodos, população sem oferta, menor intervalo,
  % interpolado, razão grade/INE e situação dos dados. **Sem classificação nem índice.**

## Resultados principais (população estimada pela grade: 684.251 hab.)

| | Manhã | Entrepico | Tarde |
|---|---|---|---|
| Viagens programadas na rede (≥ 1 partida na janela) | 1.256 | 1.286 | 1.058 |
| Linhas na rede / linhas-sentido | 48 / 96 | 49 / 98 | 48 / 96 |
| Média de linhas acessíveis por morador¹ | 3,55 | 3,62 | 3,58 |
| Média de partidas/h acessíveis por morador¹ | 29,8 | 30,7 | 25,2 |
| Idem, só moradores cobertos | 3,76 linhas · 31,6/h | 3,83 · 32,5/h | 3,79 · 26,7/h |
| Coberto em 400 m, mas sem partida no período | 5.621 hab. | 0 | 0 |
| Sem oferta acessível (sem cobertura + coberto sem serviço) | 6,43% | 5,61% | 5,61% |
| Não determinado | 192 hab. | 192 | 192 |

¹ Ponderada pela população com acessibilidade determinada; sem cobertura entra como 0.

- **Rede × acessível:** total programado na rede (1.256 viagens) e oferta acessível ao morador médio (~60 viagens em 2 h)
  são grandezas diferentes. 1.247 das 1.256 viagens da manhã passam por alguma parada acessível a alguma origem.
- **Linhas fora das janelas:** as noturnas A1–A8 não operam em nenhuma das três janelas. A C5 (Circular Centro) começa
  depois das 10h, o que deixa 5.621 hab. do distrito 01 sem partida pela manhã. A 38 não tem partida das 17h às 19h.
- **Entre períodos:** a tarde tem ~16% menos viagens na rede e ~15% menos partidas/h acessíveis que a manhã
  (mediana por seção: −14%; 475 das 521 seções caem). O número de linhas quase não muda: a redução é de frequência,
  não de linhas.
- **Território (exploratório):**
  - nos distritos censitários 03 e 02, a média de partidas/h pela manhã fica em 54 e 47; nos distritos 04, 09 e 10, entre 19 e 22;
  - partidas/h e linhas acessíveis estão fortemente correlacionadas entre seções (r = 0,95);
  - a correlação com a densidade é fraca (r = 0,16);
  - há seções densas, acima de 20 mil hab./km², com 0–5 partidas/h. É o caso de 4109101028, 4109101033, 4109106003
    e 4109106007. Isso é matéria para a Etapa 4.
- **Exemplos de linha-sentido** (manhã, na parada de referência): linha 02, ~6,5 min; TB1, 13 e C2, 5–6 min; C6A/C6B e
  38A, 40–75 min.

## Horários interpolados

- **Estrutura conferida:** viagem, linha, sentido, parada, sequência (= distância acumulada em m), partida em segundos,
  origem do horário e pontos de controle. Não há regressões, e todos os interpolados ficam entre os controles.
  A interpolação **não foi refeita**.
- **Participação:** 77% dos embarques representativos e 77,3–77,4% das partidas por parada têm horário interpolado.
- **Sensibilidade** (`analise.sensibilidade_resumo`): horários explícitos fixos; os interpolados foram deslocados de ±2 min
  (cerca de 1/4 do intervalo mediano de 8 min entre controles), sem sair da faixa entre controles. Também se calcularam
  envoltórias extremas, com o horário em qualquer ponto entre os controles:

  | Cenário | Média de partidas/h | Spearman entre seções |
  |---|---|---|
  | ±2 min | −0,4% a +0,5% | ≥ 0,9996 |
  | Envoltórias extremas | −8,1% a +8,3% | ≥ 0,998 |

  No cenário de ±2 min, no máximo 2 seções variam mais de 10%. Nas envoltórias, as linhas acessíveis praticamente não
  mudam (−0,07%). **A interpolação não altera de forma material os resultados nem as comparações entre seções.**
  As envoltórias são limites lógicos, não intervalos de confiança. Os horários de referência continuam sendo os interpolados.

## Tabelas e views criadas no schema `analise`

**Tabelas:** `partidas_dia`, `partidas_periodo`, `oferta_linha_sentido_periodo`, `origem_viagem_periodo`,
`origem_linha_sentido_periodo`, `oferta_origem_periodo`, `oferta_seccion_periodo`, `indicadores_seccion_oferta`,
`sintese_oferta_municipal`, `sensibilidade_partidas`, `sensibilidade_origem`, `sensibilidade_resumo`.

**Views:** `v_oferta_distrito_periodo`, `v_secciones_oferta`, `v_secciones_oferta_periodo`, `v_pontos_oferta_periodo`,
`v_partidas_fronteira`.

As tabelas e views da Etapa 2 foram preservadas.

**Exportações** (`resultados/etapa3/`, decimais com 4 casas):
- indicadores por seção e período e tabela larga para a Etapa 4;
- síntese municipal e resumo por distrito;
- oferta da rede por linha-sentido;
- oferta por origem e por origem × linha-sentido;
- deduplicação (`origem_viagem_periodo.csv.gz`);
- sensibilidade e partidas nas fronteiras;
- `etapa3_oferta_preliminar.gpkg`, com as camadas de seções, seções × período e pontos × período.

## Limitações

- **O que se mede:** oferta programada, não realizada; sem pontualidade, lotação, transbordos nem destinos alcançáveis.
- **Contagem por janela:** `n_viagens` da rede inclui viagens que só começam ou terminam dentro da janela. A frequência em
  uma parada está em `partidas_hora_parada_referencia`.
- **População:** as médias por seção herdam a aproximação da grade (razão grade/INE de 0,26 a 3,2; ver Etapa 2).
- **Linhas:** a definição por `route_id` conta como linhas distintas variantes comerciais do mesmo eixo (C6A/C6B, 38/38A).
- **Horários:** 77% interpolados. A sensibilidade é baixa, mas os horários exatos por parada não são publicados pela TUSSAM no feed.
