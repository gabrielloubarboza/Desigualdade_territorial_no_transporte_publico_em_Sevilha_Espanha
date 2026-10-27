# Testes de integridade — Etapa 1

Execução: 2026-10-25T02:54:30+00:00 — OK: 13, LIMITACAO: 5, FALHA: 0

Gerado por `scripts/05_testes_integridade.py` (também gravado em `qa.resultado_testes`).

| ID | Grupo | Verificação | Status | Detalhe |
|---|---|---|---|---|
| T01 | GTFS | GTFS obtido, íntegro e com arquivos obrigatórios | **OK** | md5 confere; arquivos: ['agency.txt', 'calendar.txt', 'calendar_dates.txt', 'feed_info.txt', 'routes.txt', 'stop_times.txt', 'stops.txt', 'trips.txt']; ausentes opcionais: frequencies.txt, shapes.txt |
| T01b | GTFS | Fuso horário da agência | **OK** | Europe/Madrid em 1 agência(s) |
| T01c | GTFS | Natureza dos horários (explícitos x interpolados) | **LIMITACAO** | 140063 de 509623 registros com horário explícito (27.5%); 369560 sem horário (paradas entre pontos de controle), interpolados por distância em prep.gtfs_horarios_dia e marcados como 'interpolado'. Sensibilidade: manha: 2415 de 18380 passagens com horário interpolado em trecho que cruza o limite da janela (13.1%); meio_dia: 2885 de 18915 passagens com horário interpolado em trecho que cruza o limite da janela (15.3%); tarde: 2271 de 15735 passagens com horário interpolado em trecho que cruza o limite da janela (14.4%) |
| T02 | GTFS | Serviço utilizável no dia de referência | **OK** | 2026-10-21 (Wednesday); serviços ativos: INVLAB40; 8080 viagens de ônibus; dentro de feed_info: True |
| T02b | GTFS | Feriados codificados no calendário | **LIMITACAO** | calendar_dates.txt vazio: feriados da vigência (12/10, 02/11, 07/12, 08/12, 25/12, 01/01, 06/01) não têm exceção no feed; o dia de referência não é feriado (Decreto 101/2025 Junta de Andalucía) |
| T03 | GTFS | Rotas de ônibus separadas dos demais modos | **OK** | 58 rotas de ônibus incluídas; excluídas: T1 (0); viagens não-ônibus no dia: 0 |
| T04 | GTFS | Paradas com coordenadas válidas | **OK** | 1055 paradas; 0 fora da caixa de Sevilla; 7 fora do limite municipal (4 com ônibus no dia de referência) — mantidas, pois atendem população do município |
| T05 | GTFS | Consistência entre linhas, viagens, paradas e horários | **OK** | viagens sem stop_times: 0; viagens sem serviço: 0; stop_times do dia 151543 = horários preparados 151543; partidas nulas: 0; regressões temporais: 0 (FKs ativas) |
| T05b | GTFS | Plausibilidade das velocidades entre pontos de controle | **OK** | 0 de 32222 trechos entre pontos de controle acima de 60 km/h no dia de referência |
| T06 | Carga | Ausência de duplicações indevidas | **OK** | duplicatas — stop_times: 0, stops: 0, seções: 0, células: 0, arestas: 0; registros repetidos na camada IDE de paradas: 0 |
| T07 | Seções | Seções com geometria válida, IDs únicos e sem sobreposição | **OK** | 521 seções, 521 códigos únicos; inválidas na origem: 0; inválidas após preparo: 0; sobreposições > 1 m²: 0 (0.0 m²); menor área 13250 m²; soma 141.45 km² |
| T08 | População | População por seção vinculável e coerente com o total municipal | **OK** | 521 de 521 seções vinculadas (521 registros 2024); soma 686741 = total municipal 686741; inconsistências sexo/nacionalidade: 0; nenhum valor suprimido por sigilo |
| T09 | Grade IECA | Células únicas, válidas e valores interpretados conforme a documentação | **LIMITACAO** | 887 células intersectam Sevilla (887 códigos únicos), soma pob_tot 686050; 59 com total convencional 2 (sigilo); 715 com categorias suprimidas (nota -1); 37 células multimunicipais (6902 hab., total não separável por município); relação com seções: 147 contidas em uma, 703 em várias, 37 parcialmente fora; mínimo 2 |
| T10 | Limite/CRS | Limite municipal válido e geometrias preparadas em EPSG:25830 | **OK** | área INE 141.452 km², IGN 142.131 km²; só INE 0.548 km², só IGN 1.227 km², Hausdorff 211.8 m; partes INE 2, anéis internos 0; tabelas prep fora de 25830: [] |
| T11 | Rede OSM | Arestas com comprimento positivo | **OK** | 47443 arestas, 3005.8 km; comprimento <= 0: 0; geometria nula: 0; dif. máx. ST_Length x comprimento 0.000 m; pontes 347, túneis/passagens 319; marcadas: acesso restrito 246, via de alta capacidade 364, via exclusiva de ônibus 83 |
| T12 | Rede OSM | Conectividade conhecida e componentes isolados identificados | **LIMITACAO** | 232 componentes; principal com 30941 de 31860 nós (97.12%); 212 componentes com < 10 nós (preservados, não conectados artificialmente); paradas com ônibus cujo nó mais próximo está fora do componente principal: 12 de 1027; maior distância parada-nó 228 m |
| T13 | Carga | Contagens no PostgreSQL iguais às dos arquivos originais | **OK** | todas conferem |
| T14 | Paradas | Correspondência entre paradas GTFS e camada oficial (IDE Sevilla) | **LIMITACAO** | situações: {"mesmo_id_distante": 3, "so_gtfs": 6, "mesmo_id_coerente": 1046}; paradas só no GTFS com ônibus no dia: 6; pares linha-parada com stop_sequence = Distancia IDE: 2148 de 2414; pares de paradas GTFS a < 15 m com IDs distintos: 58 |
