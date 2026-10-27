# Desigualdade territorial na oferta de ônibus urbanos em Sevilha (ES)

**[English version](README.md)** · **Página no portfólio:** https://gabrielloubarboza.github.io/projetos/sevilha/

Quais seções censitárias de Sevilha combinam **elevada densidade populacional** com **oferta relativamente
insuficiente de ônibus urbanos**, e em que consiste essa insuficiência em cada caso? A oferta é medida em três
dimensões separadas: parada com serviço a até 400 m pela rede de pedestres, número de linhas distintas e partidas
programadas por hora, sem contar duas vezes a mesma viagem.

Autor: **Gabriel Barboza Lourenço** · PostgreSQL/PostGIS · Python (OSMnx, NetworkX, GeoPandas) · GTFS · QGIS/PyQGIS

<p align="center"><img src="produtos/figuras/figuras_pt/mapa_prioritarias.png" width="640"
alt="As 33 seções prioritárias por tipo de deficiência"></p>

## Fontes

| Fonte | Uso | Data |
|---|---|---|
| INE — Censo Anual de Población (tabela 69258) | população oficial por seção (686.741) | 01/01/2024 |
| INE — seccionado (SECC_CE_20240101) | 521 seções, área, densidade (EPSG:25830) | 01/01/2024 |
| IECA — malha de população 250 m (`grid:gridp_250`) | localização aproximada dos moradores (887 células) | 01/01/2024 |
| GTFS TUSSAM — Punto de Acceso Nacional (Powered by MITRAMS) | paradas, linhas, viagens e horários | versão 20260928 |
| OpenStreetMap (OSMnx) | rede de pedestres, rios, ferrovias e autovias | 25/10/2026 |
| IDE Sevilla — camadas TUSSAM | **apenas controle de qualidade local** (redistribuição proibida) | 20/10/2026 |

Escopo: ônibus urbano TUSSAM em dia útil de referência (21/10/2026), faixas 07–09, 12–14 e 17–19. Metrô, bonde,
cercanías e ônibus metropolitanos não entram; pontualidade e demanda não são medidas.

## Principais resultados

| Indicador | Valor |
|---|---:|
| População com parada com serviço a até 400 m a pé | **94,36%** (645.680; percurso médio de 209 m) |
| População sem parada a 400 m | 38.379 (5,61%) |
| Linhas ao alcance no pico da manhã (morador médio) | 3,55 |
| Partidas acessíveis por hora, manhã → tarde | 29,8 → 25,2 (**−15,5%**) |
| Seções de alta densidade (quartil superior, ≥ 30.976,8 hab./km²) | 131 (163.874 habitantes) |
| **Seções prioritárias** (alta densidade + ≥ 1 deficiência relativa) | **33 (41.208 habitantes, 6,0%)** |
| … com poucas linhas **e** baixa frequência (tipo D) | 18 |

A baixa frequência das prioritárias é estrutural: 22 das 23 com baixa frequência pela manhã a mantêm nas três faixas.
Falta de parada (tipo A) em Los Remedios e Triana; serviço fraco (tipos B–D) em Cerro-Amate, Triana, Norte,
Este-Alcosa-Torreblanca, San Pablo-Santa Justa, Macarena e Sur.
Tabelas: `resultados/etapa2/sintese_municipal.csv`, `resultados/etapa4/sintese_municipal.csv`,
`resultados/etapa4/sintese_tipologia.csv`, `resultados/etapa4/ranking_prioritarias.csv`.

## Estrutura

```
config/            config.yaml (todos os parâmetros e fontes; reconstruído — ver "Reprodução")
scripts/           pipeline 01–22, comum.py, rede_acessibilidade.py, visual.py, executar_etapa1–5.ps1
sql/               00 banco, 01–04 fontes e QA, 05–08 acessibilidade, 09–12 oferta programada, 13–14 diagnóstico
data/              manifesto_fontes.json (URLs, versões, hashes); processed/*.json contagens de carga e inspeção do GTFS
resultados/        tabelas CSV e gráficos das etapas 2–4 (GeoPackages intermediários não versionados)
produtos/          sevilla_oferta_bus.qgz, dois GeoPackages finais, figuras (ES e figuras_pt/)
assets/fonts/      IBM Plex Sans (SIL OFL 1.1)
docs/              metodologia (etapas 1–4), testes, fontes, notas do GTFS, licenças de dados, código em destaque
```

## GeoPackages (EPSG:25830, ETRS89 / UTM 30N)

| Arquivo | Camadas | Licença |
|---|---|---|
| `produtos/sevilla_oferta_bus_resultados.gpkg` | seções com todos os indicadores (521), seções prioritárias (33), distritos (11), limite municipal (dissolução do seccionado INE), células IECA (887), pontos de demanda (2.674), paradas do GTFS (1.043), contexto regional; dicionário de campos e metadados | INE (citar a fonte), IECA CC BY 4.0, "Powered by MITRAMS" |
| `produtos/sevilla_oferta_bus_contexto_osm.gpkg` | rede de pedestres (47.443), barreiras (polígonos e linhas) | **ODbL 1.0** |

## Reprodução

Requisitos: PostgreSQL + PostGIS, Python 3.12+ (`requirements.txt`; versões exatas em `requirements-lock.txt`),
QGIS 3.40 LTR para o projeto e os estilos.

```powershell
python -m venv .venv; .venv\Scripts\pip install -r requirements.txt
psql -U postgres -v owner=gis_portfolio -f sql\00_criar_banco.sql   # depois, acrescente a senha ao seu pgpass (manual)
powershell -File scripts\executar_etapa1.ps1    # downloads, rede OSM, carga, testes de integridade
powershell -File scripts\executar_etapa2.ps1    # acessibilidade a pé, 400 m
powershell -File scripts\executar_etapa3.ps1    # oferta programada a partir do GTFS
powershell -File scripts\executar_etapa4.ps1    # densidade, limiares, tipologia, ranking
```

**Observações importantes**
- `config/config.yaml` **não estava no acervo do projeto** e foi reconstruído a partir dos parâmetros que a execução
  original gravou no banco (`prep.parametros`, `analise.parametros`, `prep.periodos_analise`) e de
  `data/manifesto_fontes.json`; cada valor traz a sua evidência. Os testes das etapas 2, 3 e 4 (scripts 08, 11 e 14)
  foram executados com ele contra o banco original em 27/10/2026.
- `config/paleta.json` (paleta usada por `visual.py`, `16_geopackages_finales.py`, `17_figuras.py`,
  `18_informe_pdf.py` e pelos estilos QGIS) **também está ausente** e não pôde ser recuperado: a **etapa 5 (estilos
  finais, figuras e relatório) não pode ser reexecutada** a partir deste repositório. Os GeoPackages e figuras
  publicados são as saídas originais da etapa 5.
- O GTFS no Punto de Acceso Nacional exige chave de API; o pipeline usa o espelho público da Mobility Database com
  URL versionada e conferência de MD5. As camadas da IDE Sevilla são baixadas só para controle local.
- Fontes on-line mudam: uma nova execução reflete os dados disponíveis na data.

## Limitações

- Oferta programada (GTFS), não pontualidade real nem demanda; 77% dos horários por parada são interpolados
  (sensibilidade de ±2 min altera a frequência média em menos de 0,5%).
- Limiares relativos e internos a Sevilha, não padrões técnicos ou legais; há seções com deficiências graves e
  densidade intermediária fora das 33.
- A população da grade IECA difere do total do INE por seção; a densidade usa a área total da seção.
- Rede OSM sem calçadas explícitas; autovias sem passagem de pedestres excluídas.

## Licença

Código original — [MIT](LICENSE), © 2026 Gabriel Barboza Lourenço (somente o código). Dados, tabelas derivadas,
GeoPackages e figuras seguem as condições de cada fonte — ver [`docs/licencias_datos.md`](docs/licencias_datos.md).
IBM Plex: SIL OFL 1.1.
