# GTFS TUSSAM — inspeção e adequação metodológica

Resumo gerado por `scripts/02_inspecionar_gtfs.py` (detalhe em `data/processed/gtfs_inspecao.json`).

## Estrutura

| Arquivo | Registros | Observação |
|---|---|---|
| agency.txt | 1 | TUSSAM, `Europe/Madrid` |
| feed_info.txt | 1 | `feed_version` 20260928, vigência 2026-09-28 a 2027-01-17 |
| routes.txt | 59 | 58 `route_type=3` (ônibus) + 1 `route_type=0` (T1 Metrocentro) |
| trips.txt | 27.845 | `shape_id` e `block_id` vazios |
| stop_times.txt | 509.623 | ver "Horários" |
| stops.txt | 1.055 | sem `location_type`/estações; 1.043 servidas por ônibus, 12 só pelo bonde |
| calendar.txt | 4 | INVLAB40 (seg–qui), INVVIE40 (sex), INVSAB40 (sáb), INVFES40 (dom/feriado) |
| calendar_dates.txt | 0 | vazio: feriados não codificados |
| frequencies.txt, shapes.txt | — | ausentes (opcionais) |

Ônibus e bonde estão no mesmo feed. A separação usa `route_type` (campo do próprio feed, não nomes):
`prep.gtfs_rotas.incluida_analise = (route_type = 3 AND agency_id = 'TUSSAM')`. As linhas noturnas (A1–A8), a EA
(Aeropuerto) e as circulares são serviços regulares TUSSAM de ônibus e ficam incluídas. A linha 53 só tem serviço em
sábado/domingo.

## Horários

- **27,5%** dos registros (140.063) têm `arrival_time`/`departure_time` explícitos. São os pontos de controle,
  em média 5 por viagem. Os outros **72,5%** estão em branco. Não há coluna `timepoint` nem `frequencies.txt`.
- Primeira e última parada de toda viagem têm horário. Nenhuma viagem fica sem horário, não há intervalos
  negativos ou nulos e `arrival_time = departure_time` sempre.
- Horários de 04:30:00 a 30:00:00. Há 3.258 registros ≥ 24:00:00 (serviço noturno), tratados como segundos do dia de serviço.
- Intervalo entre pontos de controle: mediana de 8 min (máx. 31). Entre dois controles há em média 4 paradas sem horário (máx. 20).
- **`stop_sequence` é a distância acumulada em metros ao longo do percurso.** A razão entre a diferença de
  `stop_sequence` e a distância euclidiana entre paradas consecutivas tem mediana 1,04 e só 0,17% de casos abaixo de 0,95.
  A velocidade comercial resultante tem mediana de 12,6 km/h. Em 2.148 de 2.414 pares linha–parada, o valor coincide
  exatamente com o campo `Distancia` da camada oficial da IDE.

**Consequência.** As partidas programadas podem ser calculadas em todas as paradas. Nas paradas sem horário, ele é
**interpolado linearmente pela distância** entre os pontos de controle anterior e seguinte, que é o tratamento
previsto pela especificação GTFS para horários ausentes. Resultado em `prep.gtfs_horarios_dia`, com
`origem_horario` = `explicito` | `interpolado` e os horários dos controles que delimitam cada interpolação.
No dia de referência, 73,4% das 151.543 passagens de ônibus são interpoladas. Horários interpolados são estimativas
da programação, não horários publicados.

**Sensibilidade.** Entre 13% e 15% das passagens interpoladas que caem dentro de uma janela de 2 h ficam em trechos
que cruzam o início ou o fim da janela. Essas podem mudar de janela com um erro de poucos minutos. O efeito sobre
contagens de 2 h tende a se compensar, mas deve ser testado na etapa de frequências.

## Dia de referência

**Quarta-feira, 21/10/2026.** Está dentro de `feed_info` e de `calendar`, não é feriado (Decreto 101/2025 da Junta
de Andalucía) e cai fora de Navidad. Serviço ativo: `INVLAB40`, idêntico de segunda a quinta. São 8.080 viagens de
ônibus em 57 linhas, mais 256 de bonde, que ficam excluídas.

Janelas preparadas em `prep.periodos_analise` (intervalo [início, fim)): 07:00–09:00, 12:00–14:00, 17:00–19:00.
Para referência, viagens de ônibus em curso em cada janela: 1.273, 1.322 e 1.091. Isso não é indicador por parada.

Limitação: `calendar_dates.txt` vazio. Nos feriados da vigência (12/10, 02/11, 07/12, 08/12, 25/12, 01/01, 06/01), o
feed aplicaria o serviço de dia útil. Isso não afeta o dia escolhido.

## Paradas: GTFS × camada oficial (IDE Sevilla, 20/10/2026)

`stop_id` do GTFS = `Nodo` da camada IDE. Linhas: os 59 `route_id` = `Linea` da IDE, sem diferenças.

| Situação | Paradas |
|---|---|
| mesmo ID, posição coerente (≤ 25 m) | 1.046 |
| mesmo ID, posição distante | 3 (1112: 86 m; 784: 135 m; 1113: nome e local diferentes, 4,3 km) |
| só no GTFS | 6 (Reina Mercedes e Alf. Lasso de la Vega, todas com serviço no dia) |
| só na IDE | 0 |

A camada IDE (20/10) é mais recente que o GTFS (28/09). As divergências se concentram em Reina Mercedes, Puerta
Osario e Gta. Parias Merry, o que indica mudanças de itinerário ou de paradas posteriores ao feed. Elas também explicam
parte dos pares linha–parada cuja distância difere, concentrados nas linhas 2, 3, 6, 10, 32 e 34. **O GTFS continua sendo a
referência da oferta programada**: a IDE serve só para conferência, e nenhum ID ou horário foi substituído. Há 58 pares de
paradas GTFS a menos de 15 m com IDs distintos, em geral sentidos opostos ou baias contíguas. São mantidos.
