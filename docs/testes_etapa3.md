# Testes de integridade — Etapa 3

Execução: 2026-10-25T15:20:24+00:00 — OK: 15, LIMITACAO: 0, FALHA: 0

Gerado por `scripts/11_testes_etapa3.py` (também em `qa.resultado_testes`, IDs com prefixo F).

| ID | Grupo | Verificação | Status | Detalhe |
|---|---|---|---|---|
| F01 | GTFS | Serviços GTFS correspondem à data de referência | **OK** | serviços nas partidas: INVLAB40; ativos em 2026-10-21: INVLAB40; partidas fora do calendário de quarta-feira: 0; exceções calendar_dates na data: 0 |
| F02 | GTFS | Sem bonde T1 ou outros modos | **OK** | partidas não-ônibus: 0; de outro operador: 0; linhas de ônibus com partidas no dia: 57 |
| F03 | Períodos | Partidas atribuídas corretamente aos três períodos [início, fim) | **OK** | fora da janela: 0; partidas do dia nas janelas 50307 = registradas 50307; em dois períodos: 0; exatamente no início: 107 (todas incluídas: 107); exatamente no fim: 111 (incluídas no período que termina: 0) |
| F04 | GTFS | Horários válidos e cronologicamente coerentes | **OK** | inválidos: 0; regressões na viagem: 0; interpolados fora dos pontos de controle: 0; maior horário após 24h corresponde a 02:58 do dia seguinte (< 07:00: viagens do dia anterior não invadem as janelas) |
| F05 | Paradas | Paradas acessíveis correspondem a paradas com programação | **OK** | 981 paradas acessíveis; sem nenhuma partida no dia: 0; sem partida no período (informativo) — manha: 33, meio_dia: 19, tarde: 19 |
| F06 | Deduplicação | Mesma viagem contada uma vez por origem e período | **OK** | duplicatas origem-período-viagem: 0; n_viagens divergente da tabela deduplicada: 0; passagens brutas removidas pela deduplicação: 230199; viagens acessíveis em >1 parada: 184475; embarque fora da menor caminhada: 0 |
| F07 | Contagens | Linhas distintas, viagens e linhas-sentido conferem com recálculo independente | **OK** | 6978 pares origem-período com oferta comparados; presentes só de um lado: 0; divergências: {'n_viagens': 0, 'n_linhas': 0, 'n_linha_sentido': 0} |
| F08 | Sentidos | Sentidos das viagens preservados | **OK** | direction_id divergente do GTFS: 0; nulos: 0; origens com linha-sentido fora de [linhas, 2·linhas]: 0 |
| F09 | Contagens | Partidas por hora = viagens / duração da janela | **OK** | desvio máx. origem 0E-32; linha-sentido 0E-20; rede 0E-32 |
| F10 | Classificação | Nulos (não determinado), zeros (sem cobertura / sem serviço) e com serviço coerentes | **OK** | incoerências — ND com valor: 0; sem cobertura com oferta: 0; coberto sem serviço incoerente: 0; com serviço sem viagens: 0; determinado com nulo: 0; situações: coberto_sem_servico_no_periodo,com_servico,nao_determinado,sem_cobertura_400m |
| F11 | Agregação | Médias ponderadas pela população conferem com recálculo independente | **OK** | desvio máx. — média de linhas 3.6e-15; partidas/h 2.8e-14; % com serviço 2.8e-14 |
| F12 | Seções | 521 seções preservadas com geometria original | **OK** | 1563 linhas seção-período (521 seções); tabela larga: 521; seções sem média calculável: 0; geometrias alteradas: 0 |
| F13 | Agregação | Coerência entre origens, seções e município | **OK** | desvios máx. — com serviço origem x seção 5.8e-10; coberto sem serviço 9.1e-13; pop. 2.3e-10; seção x município 5.8e-10; média partidas/h seção x município 6.0e-14; soma das categorias 0.0e+00 |
| F14 | Sensibilidade | Indicadores pouco sensíveis à interpolação dos horários | **OK** | ±2 min: média de partidas/h varia -0.40% a +0.47%, Spearman das seções >= 0.9996, seções com variação > 10%: até 2; envoltórias extremas (horário em qualquer ponto entre controles): -8.1% a +8.3%, Spearman >= 0.9979, linhas -0.07% a -0.00% |
| F15 | Reprodução | Resultados idênticos em segunda execução do SQL da etapa | **OK** | oferta_origem_periodo: igual (8022 linhas); origem_viagem_periodo: igual (423277 linhas); origem_linha_sentido_periodo: igual (41383 linhas); oferta_seccion_periodo: igual (1563 linhas); sintese_oferta_municipal: igual (3 linhas); sensibilidade_resumo: igual (15 linhas) |

## Casos representativos

Linhas acessíveis no formato `linha/sentido:viagens`. Passagens brutas = viagem × parada antes da deduplicação.

| Caso | Origem | Período | Situação | Paradas 400 m | Paradas com partida | Linhas | Linha-sentido | Viagens | Partidas/h | Passagens brutas | Linhas acessíveis |
|---|---|---|---|---|---|---|---|---|---|---|---|
| muitas paradas acessíveis | 3412_4109105023 | manha | com_servico | 25 | 25 | 23 | 32 | 339 | 169.5 | 370 | 01/0:15 01/1:14 05/0:11 05/1:11 21/0:7 21/1:7 22/1:10 25/1:9 26/1:9 27/1:13 28/1:13 29/1:18 30/1:7 31/1:7 34/0:11 34/1:11 37/0:11 37/1:10 38/1:4 38A/1:2 C1/0:20 |
| muitas paradas acessíveis | 3412_4109105023 | meio_dia | com_servico | 25 | 25 | 24 | 33 | 341 | 170.5 | 372 | 01/0:14 01/1:14 05/0:10 05/1:10 21/0:7 21/1:7 22/1:11 25/1:9 26/1:9 27/1:12 28/1:14 29/1:18 30/1:7 31/1:7 34/0:11 34/1:12 37/0:12 37/1:13 38/1:1 38A/1:2 C1/0:21 |
| muitas paradas acessíveis | 3412_4109105023 | tarde | com_servico | 25 | 25 | 23 | 32 | 297 | 148.5 | 326 | 01/0:11 01/1:11 05/0:9 05/1:9 21/0:6 21/1:6 22/1:8 25/1:9 26/1:10 27/1:10 28/1:11 29/1:12 30/1:7 31/1:6 34/0:12 34/1:12 37/0:10 37/1:10 38A/1:2 C1/0:17 C2/0:16  |
| mesma viagem em várias paradas | 2994_4109107018 | manha | com_servico | 10 | 10 | 3 | 5 | 43 | 21.5 | 118 | 03/0:10 03/1:9 10/0:10 10/1:11 C6A/1:3 |
| mesma viagem em várias paradas | 2994_4109107018 | meio_dia | com_servico | 10 | 10 | 3 | 5 | 42 | 21.0 | 122 | 03/0:10 03/1:10 10/0:10 10/1:11 C6A/1:1 |
| mesma viagem em várias paradas | 2994_4109107018 | tarde | com_servico | 10 | 10 | 3 | 5 | 33 | 16.5 | 92 | 03/0:9 03/1:9 10/0:6 10/1:7 C6A/1:2 |
| uma única linha | 3478_4109104042 | manha | com_servico | 2 | 2 | 1 | 2 | 22 | 11.0 | 22 | 05/0:11 05/1:11 |
| uma única linha | 3478_4109104042 | meio_dia | com_servico | 2 | 2 | 1 | 2 | 22 | 11.0 | 22 | 05/0:11 05/1:11 |
| uma única linha | 3478_4109104042 | tarde | com_servico | 2 | 2 | 1 | 2 | 20 | 10.0 | 20 | 05/0:10 05/1:10 |
| coberta sem partida no período | 3217_4109101029 | manha | coberto_sem_servico_no_periodo | 1 | 0 | 0 | 0 | 0 | 0.0 | 0 | — |
| coberta sem partida no período | 3217_4109101029 | meio_dia | com_servico | 1 | 1 | 1 | 1 | 4 | 2.0 | 4 | C5/0:4 |
| coberta sem partida no período | 3217_4109101029 | tarde | com_servico | 1 | 1 | 1 | 1 | 4 | 2.0 | 4 | C5/0:4 |
| sem cobertura 400 m | 3671_4109104063 | manha | sem_cobertura_400m | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 | — |
| sem cobertura 400 m | 3671_4109104063 | meio_dia | sem_cobertura_400m | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 | — |
| sem cobertura 400 m | 3671_4109104063 | tarde | sem_cobertura_400m | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 | — |
| acessibilidade não determinada | 3305_4109109033 | manha | nao_determinado | None | None | None | None | None | — | None | — |
| acessibilidade não determinada | 3305_4109109033 | meio_dia | nao_determinado | None | None | None | None | None | — | None | — |
| acessibilidade não determinada | 3305_4109109033 | tarde | nao_determinado | None | None | None | None | None | — | None | — |

Partidas próximas às fronteiras das janelas (±3 min), com o período atribuído:

| Fronteira | Linha/sentido | Viagem | Parada | Horário | Origem do horário | Faixa entre controles | Período atribuído |
|---|---|---|---|---|---|---|---|
| 07:00 | 01/0 | 6200105006 | 472 | 07:00:00 | explicito | 07:00–07:00 | manha |
| 07:00 | 27/1 | 6202711005 | 216 | 07:00:01 | interpolado | 06:52–07:02 | manha |
| 09:00 | 01/0 | 6200103008 | 220 | 09:00:00 | explicito | 09:00–09:00 | nenhum |
| 09:00 | 01/0 | 6200111008 | 566 | 09:00:00 | interpolado | 08:58–09:18 | nenhum |
| 12:00 | 02/0 | 6200209010 | 692 | 12:00:00 | explicito | 12:00–12:00 | meio_dia |
| 12:00 | 34/0 | 6203404014 | 872 | 12:00:00 | interpolado | 11:52–12:09 | meio_dia |
| 14:00 | 01/1 | 6200115013 | 785 | 14:00:00 | explicito | 14:00–14:00 | nenhum |
| 14:00 | C2/1 | 6208216013 | 203 | 14:00:00 | interpolado | 13:56–14:10 | nenhum |
| 17:00 | 01/0 | 6200103018 | 430 | 17:00:00 | explicito | 17:00–17:00 | tarde |
| 17:00 | 12/0 | 6201212020 | 847 | 17:00:00 | interpolado | 16:58–17:09 | tarde |
| 19:00 | 02/0 | 6200208016 | 863 | 19:00:00 | explicito | 19:00–19:00 | nenhum |
| 19:00 | 03/1 | 6200301011 | 946 | 18:59:59 | interpolado | 18:56–19:07 | tarde |
