# Testes de integridade — Etapa 4

Execução: 2026-10-25T15:20:40+00:00 — OK: 13, LIMITACAO: 0, FALHA: 0

Gerado por `scripts/14_testes_etapa4.py` (também em `qa.resultado_testes`, IDs com prefixo G). Limiares, flags,
tipologia e ranking são recalculados de forma independente em pandas.

| ID | Grupo | Verificação | Status | Detalhe |
|---|---|---|---|---|
| G01 | Seções | 521 seções preservadas com geometria INE em EPSG:25830 | **OK** | 521 seções na tabela consolidada; 1042 linhas seção x cenário; geometrias alteradas: 0; SRID diferente: 0 |
| G02 | Seções | Sem duplicação de códigos | **OK** | 521 linhas, 521 códigos distintos |
| G03 | Densidade | Densidade = população INE / área total da seção | **OK** | desvio relativo máx. frente ao recálculo (ST_Area em EPSG:25830, população 2024): 0.0e+00 |
| G04 | Limiares | Limiares e flags aplicados corretamente (dois cenários) | **OK** | desvio máx. dos limiares: 3.6e-12; flags divergentes: {'principal': 0, 'sensibilidade_tercis': 0} |
| G05 | Classificação | Indicadores binários coerentes | **OK** | incoerências — contagem: 0; texto: 0; nulos fora das seções sem cobertos: 0; prioritária: 0; dimensões: 0; seções sem população coberta (diversidade/frequência não se aplicam): 2 |
| G06 | Tipologia | Uma categoria principal por seção, conforme a precedência | **OK** | divergências frente ao recálculo: 0; sem categoria: 0 |
| G07 | Ranking | Ranking determinístico, contínuo e único | **OK** | 33 prioritárias com postos 1..33 únicos; divergências frente ao recálculo: 0; posto fora das prioritárias: 0 |
| G08 | Preservação | População e indicadores originais preservados | **OK** | população INE 686741 = 686741; grade 684251.15 = pontos 684251.15; seções com indicador da Etapa 3 alterado: 0 |
| G09 | Agregação | Seção, tipologia, distrito e município coerentes | **OK** | distritos: 521 seções, 686741 hab.; prioritárias distritos 33 = município 33 = tipos A–D 33; população prioritária 41208 = 41208; tipologias: 521 seções, 686741 hab.; soma das participações distritais 100.000000000% |
| G10 | Nulos | Nulos e denominadores zero tratados explicitamente | **OK** | variação % nula sem manhã = 0: 0 incoerências; seções com manhã = 0 (variação indefinida): 5; sem população coberta (médias entre cobertos nulas): 2; densidade de área habitada nula: 0; nulos indevidos: 0 |
| G11 | Períodos | Diferenças entre períodos coerentes | **OK** | desvio máx. da diferença: 0.0e+00; seções com redução à tarde: 475 (Etapa 3: 475); padrões incoerentes: 0 |
| G12 | Reprodução | Resultados idênticos após nova execução | **OK** | diag_resultado_seccion: igual; diag_limiares: igual; diag_sintese_distrito: igual; diag_sintese_municipal: igual; diag_sensibilidade_resumo: igual; diag_densidade_relacao: igual |
| G13 | Sensibilidade | Prioritárias por quartis permanecem prioritárias com tercis | **OK** | nos dois: 33; só quartis: 0; só tercis: 25; top 10 também no top 20 por tercis: 10; Spearman dos postos comuns: 0.997; distritos com prioritárias: 9 x 9 |
