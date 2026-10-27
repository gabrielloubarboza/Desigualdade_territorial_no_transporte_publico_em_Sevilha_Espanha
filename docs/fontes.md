# Fontes de dados — Etapa 1

Manifesto completo (URLs, datas, hashes, tamanhos): [`data/manifesto_fontes.json`](../data/manifesto_fontes.json),
também carregado em `fonte.metadados_fontes`. Datas de obtenção em UTC (24/10/2026, noite, horário local).

| Fonte | Produtor | Versão / referência | Formato | Acesso | Licença / redistribuição |
|---|---|---|---|---|---|
| GTFS TUSSAM | TUSSAM, publicado no NAP (MITRAMS) | `feed_version` 20260928; vigência 28/09/2026–17/01/2027; arquivo MDB `mdb-2770-202609300035` | GTFS zip | NAP exige API key (HTTP 401/403 sem credencial). Usado o espelho público da Mobility Database com URL versionada; md5 idêntico ao `latest.zip` | Licencia de datos abiertos MITRAMS: reutilização e redistribuição permitidas citando "Powered by MITRAMS" e indicando se o dado é bruto ou processado |
| Seccionado | INE | `SECC_CE_20240101` (seções a 01/01/2024) | Shapefile, EPSG:25830 | Download direto | Aviso legal INE: reutilização citando a fonte |
| População por seção | INE — Censo Anual de Población 2021-2025 | Tabela 69258 (sexo × nacionalidade), província de Sevilla, ano 2024 (01/01/2024); publicação 29/04/2026 | CSV `;` UTF-8 com BOM (o servidor declara ISO-8859-15) | Download direto | Aviso legal INE |
| Grade de população 250 m | IECA — Distribución espacial de la población | `grid:gridp_250`, população a 01/01/2024 | WFS 2.0 → GeoJSON, EPSG:25830 | WFS público | CC BY 4.0 declarada pelo IECA desde 2014 (termos vigentes não reconfirmados) |
| Paradas TUSSAM | TUSSAM / Ayuntamiento (IDE Sevilla) | Item ArcGIS `TUSSAM_Paradas`, "actualizado a 20/10/2026" | ArcGIS FeatureServer → GeoJSON, EPSG:4326 (nativo 3857) | Público | **Termos TUSSAM proíbem redistribuir** a informação (modificada ou não) em sítio web ou outro meio. Usada só para conferência; não versionada |
| Linhas TUSSAM | idem | Item `TUSSAM_Lineas`, 20/10/2026 | idem | Público | idem |
| Limite municipal | IGN (INSPIRE AU) | Unidade 34014141091 | GML 3.2, EPSG:25830 | WFS público | CC BY 4.0 |
| Rede caminhável | OpenStreetMap via Overpass (OSMnx) | `timestamp_osm_base` 2026-10-25T02:24:51Z | GeoPackage, EPSG:25830 | Público | ODbL 1.0 |
| Barreiras e áreas não residenciais (Etapa 2) | OpenStreetMap via Overpass (OSMnx `features_from_polygon`) | água, rios/canais, ferrovias, motorway/trunk, parques, `landuse=railway`; mesma área da rede | GeoPackage, EPSG:25830 | Público | ODbL 1.0 |

Documentação do IECA preservada em `data/raw/ieca_grid/docs/` (memória técnica e informe metodológico).

## Escolhas de versão

- **GTFS**: a versão mais recente obtível. A Mobility Database consulta o NAP diariamente e registra
  essa versão como a última (`latest.zip`, de 30/09/2026). Sem API key não dá para conferir no próprio NAP se há
  arquivo mais novo. Usa-se um único feed, sem combinar calendários de versões diferentes.
- **População e seções**: ambos de 01/01/2024. A tabela do INE usa o seccionado vigente em cada ano: as 521
  seções com população em 2024 coincidem uma a uma com as 521 seções do `SECC_CE_20240101`. Outros anos têm conjuntos diferentes
  (2021: 532; 2025: 522), por isso **não** se misturam anos.
- **Grade IECA**: também 01/01/2024, mesma data de referência. As duas bases não são a mesma contagem: o INE usa o Censo
  Anual e o IECA a BDLPA, base longitudinal derivada do Padrón e geocodificada por portal. Ver `metodologia_etapa1.md`.
