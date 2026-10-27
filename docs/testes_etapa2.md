# Testes de integridade — Etapa 2

Execução: 2026-10-25T03:28:55+00:00 — OK: 12, LIMITACAO: 1, FALHA: 0

Gerado por `scripts/08_testes_etapa2.py` (também em `qa.resultado_testes`, IDs com prefixo E).

| ID | Grupo | Verificação | Status | Detalhe |
|---|---|---|---|---|
| E00 | Grade IECA | Abrangência da grade: somente células habitadas, sem registros omitidos | **OK** | WFS: 887 células com cmun contendo 41091 (carregadas: 887); células com pob_tot <= 0 em toda a Andaluzia: 0 |
| E01 | Demanda | Identificadores e população de origem preservados | **OK** | 887 de 887 células representadas; células só de Sevilla: soma 679148.00 = publicada 679148; desvio máx. célula x (pob_tot·cota) 6.82e-13; grd_fixid divergentes 0; parcelas 684251.15 = pontos 684251.15 |
| E02 | Demanda | Sem duplicação de células/parcelas entre seções | **OK** | pares célula-seção duplicados 0; desvio máx. da soma dos pesos por célula 3.3e-16; origens duplicadas 0 |
| E03 | Demanda | Pontos de demanda dentro da seção e da parcela que representam | **OK** | 2674 pontos; fora da seção 0; fora da parte habitável da parcela 0; seções sem ponto 0 |
| E04 | Paradas | Ligações das paradas espacialmente coerentes | **OK** | 1027 de 1027 paradas com serviço ligadas; ligação máx. 36.5 m; ligação fora da parada/aresta: 0/0; fora do componente principal: 650:ligada_apenas_componente_isolado, 1002:ligada_apenas_componente_isolado |
| E05 | Rede | Nenhuma ligação artificial através de barreiras | **LIMITACAO** | ligações que cruzam barreira: 0 de 3721; ligações de mão única fora do grafo (sem passagem entre componentes); arestas excluídas por atravessar água sem ponte: 4; utilizáveis que ainda dividem polígono de água: 0; amostra: 0 de 14 percursos cruzam água sem ponte, 0 cruzam ferrovia em nível (passagens OSM); sobreposições longitudinais remanescentes (margens de canais e lagos, sem travessia): 31 arestas, 5089.0 m (Canal de los Presos del Bajo Guadalquivir: 18; (sem nome): 9; Canal de Alfonso XIII: 3; Estanque parque Miraflores: 1) |
| E06 | Rede | Distâncias calculadas com o comprimento real das arestas | **OK** | amostra de 14 percursos reconstruídos no PostGIS: dif. máx. geometria x grafo 0.0000 m; pares com percurso < distância euclidiana: 0; dif. máx. ST_Length x peso da aresta 0.0e+00 m |
| E07 | Acessibilidade | Nenhum par origem-parada acima de 400 m | **OK** | 12571 pares; máximo 399.989 m; acima de 400 + 0.001 m: 0 |
| E08 | Acessibilidade | Paradas acessíveis associadas a serviço de ônibus em 21/10/2026 | **OK** | 981 paradas alcançadas; sem partidas de ônibus no dia: 0; não marcadas com serviço: 0 |
| E09 | Acessibilidade | Classificação coberto / sem cobertura / não determinado consistente | **OK** | incoerências — coberto x pares: 0; sem cobertura não ligada ao principal: 0; ND sem motivo: 0; coberto com distância > 400: 0; sem cobertura com distância <= 400: 0; mais próxima divergente: 0 |
| E10 | Agregação | Soma das categorias = população estimada da grade | **OK** | coberta 645680.3 + sem cobertura 38378.8 + ND 192.1 = 684251.15; grade 684251.15; soma das seções 684251.15 |
| E11 | Agregação | Percentuais por seção coerentes (0–100%, soma 100%) | **OK** | 521 seções (521 com população da grade); fora de 0–100%: 0; desvio máx. da soma: 5.7e-14 p.p.; seções sem população INE: 0 |
| E12 | Reprodução | Resultados idênticos em nova execução do cálculo | **OK** | pares: 12571 recalculados x 12571 gravados (iguais: True); parada mais próxima: 2656 x 2656 (iguais: True) |

## Amostra conferida (percurso reconstruído no PostGIS — `qa.amostra_percursos`)

| Contexto | Origem | Parada | Distância no grafo (m) | Comprimento geométrico (m) | Água sem ponte | Ferrovia em nível |
|---|---|---|---|---|---|---|
| central | 3284_4109101039 | 630 | 297.05 | 297.05 | False | False |
| central | 3284_4109101040 | 630 | 342.17 | 342.17 | False | False |
| central | 3285_4109101040 | 4030 | 386.24 | 386.24 | False | False |
| periferica | 50662_4109107023 | 677 | 3699.53 | 3699.53 | False | False |
| periferica | 5094_4109109018 | 493 | 715.65 | 715.65 | False | False |
| proxima_rio | 3080_4109107026 | 273 | 300.70 | 300.70 | False | False |
| proxima_rio | 3280_4109106015 | 13 | 134.62 | 134.62 | False | False |
| proxima_rio | 3408_4109106001 | 197 | 223.02 | 223.02 | False | False |
| proxima_via_expressa | 3030_4109107036 | 290 | 99.17 | 99.17 | False | False |
| proxima_via_expressa | 3403_4109106033 | 176 | 141.41 | 141.41 | False | False |
| proxima_via_expressa | 3625_4109104058 | 1010 | 193.12 | 193.12 | False | False |
| sem_cobertura_proxima_euclidiana | 3245_4109101027 | 745 | 406.21 | 406.21 | False | False |
| sem_cobertura_proxima_euclidiana | 3412_4109101037 | 591 | 421.85 | 421.85 | False | False |
| sem_cobertura_proxima_euclidiana | 3570_4109109001 | 489 | 576.32 | 576.32 | False | False |
