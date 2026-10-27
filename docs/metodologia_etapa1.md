# Metodologia e limitações — Etapa 1

## Recorte territorial e referência espacial

- **Limite principal**: dissolução das 521 seções do seccionado INE 2024 (`prep.limite_municipal`,
  `principal = true`). Ele é coerente com a população por seção. O IGN (INSPIRE AU) entra só como comparação.
- Área INE: **141,452 km²**. Área IGN: 142,131 km². Área só no INE: 0,548 km²; só no IGN: 1,227 km²; distância de Hausdorff
  entre os contornos: 212 m. As diferenças são compatíveis com escala e generalização distintas da linha-limite.
  Elas podem ser inspecionadas em `qa.v_comparacao_limites` e por diferença geométrica em `prep.limite_municipal`.
- Nas duas fontes o município tem **2 partes**: o corpo principal (140,2 km²) e um enclave de 1,3 km² ao sul
  (≈ 37,309 N, 6,025 O), que pertence à seção 4109111001.
- Todas as fontes métricas já vinham em ETRS89 / UTM 30N (EPSG:25830): INE, IGN e o WFS do IECA. A grade IECA é gerada
  em ETRS89-LAEA (EPSG:3035) e o próprio IECA a transforma para 25830, por isso as células aparecem levemente rotacionadas,
  com ≈ 62.555 m² em vez de 62.500 m². Paradas GTFS (WGS84) e IDE (3857 → 4326) foram reprojetadas para 25830 em `prep`.

## População por seção

- Fonte: INE, Censo Anual de Población, 01/01/2024, tabela 69258. População residente (definição censitária,
  base de registros). As 521 seções coincidem 1:1 com o seccionado 2024. A soma é **686.741**, igual ao total municipal.
  Não há valores suprimidos por sigilo: a menor seção tem 581 habitantes, e o INE só suprime seções com menos de 50.
- `prep.poblacion_seccion` guarda total, sexo e nacionalidade. A área está em `prep.secciones.area_km2`.
  A densidade e qualquer classificação ficam para as etapas seguintes.

## Grade IECA 250 m

- 887 células intersectam o limite INE, com soma `pob_tot` = 686.050. Desse total, 850 células são exclusivamente de Sevilla
  (679.148 hab.) e **37 são multimunicipais** (`cmun` como `41038 / 41091`, 6.902 hab.). Nessas, o total combina dois
  municípios e não pode ser separado com os dados publicados. São as mesmas 37 classificadas como `parcialmente_fora_municipio`.
- **Sigilo** (memória técnica IECA, item 7): a partir de 2024, totais comprometidos recebem o **valor convencional 2** e
  as categorias são suprimidas. Identificação: `pob_tot = 2 AND pob_m + pob_h = 0` → `sigilo_total_convencional`
  (**59 células**; não existe nenhuma célula com valor 1). A presença de `nota = '(-1) Secreto Estadístico'` → `sigilo_em_categorias`
  (715 células) indica supressão de alguma categoria, mas o total continua publicado. O impacto sobre o total é
  desprezível (≤ ~59 pessoas). Nenhum valor foi corrigido ou redistribuído.
- 2,64% da população andaluza não foi geocodificada a portal. O IECA a atribuiu de forma indireta usando as seções
  censitárias, o que reforça a coerência com o seccionado.
- **Grade × seções** (`prep.grid_seccion_intersecao`, área de interseção e fração da célula): 147 células contidas em uma
  única seção, 703 em várias e 37 parcialmente fora do município (lascas < 0,1% da célula ignoradas). Regras possíveis
  para as próximas etapas: (a) usar a grade como origem e agregar por seção pela fração de área; (b) atribuir cada célula
  à seção de maior interseção (`frac_maior_secao`). Totais INE e IECA diferem em 0,1% (686.741 × 686.050 no recorte),
  por fontes e métodos distintos. Não devem ser tratados como a mesma contagem.

## Rede caminhável (OSM)

- OSMnx 2.1.1, `network_type='walk'`, simplificada e convertida em não direcionada, área = limite + 1.000 m.
  Resultado: 31.860 nós, 47.443 arestas, **3.005,8 km**, todas com comprimento > 0. O comprimento vem de `ST_Length` em 25830.
- **Conectividade**: 232 componentes. O principal tem 30.941 nós (97,12%). Há 212 componentes com menos de 10 nós
  (calçadas mapeadas em separado, pátios, passagens) que foram preservados e identificados (`componente`, 0 = principal),
  sem nenhuma conexão artificial através de rios, ferrovias ou vias expressas.
- Marcações (nada foi removido): 347 pontes, 319 túneis/passagens cobertas, 246 arestas com `access=no/private` sem
  permissão a pedestres (`restricao_acesso`), 364 trechos `trunk`/`motorway` (`via_alta_capacidade`, aceitos pelo filtro
  `walk` do OSMnx) e 83 `busway` (`via_exclusiva_onibus`). Na Etapa 2 é preciso decidir se as arestas marcadas entram no cálculo.
- Paradas: 12 das 1.027 com ônibus no dia têm o nó mais próximo fora do componente principal, sempre a menos de 31 m.
  Em 5 paradas da periferia (Ctra. Pino Montano, Av. La Prensa, Villanueva del Pítamo), o nó mais próximo está a 103–228 m.
  **Recomendação para a Etapa 2**: projetar cada parada sobre a aresta mais próxima do componente principal
  e registrar a distância de projeção.

## Banco `sevilla_oferta_bus`

- `fonte`: dados originais (GTFS com tipos e FKs; INE, IECA, IDE, IGN e OSM como importados) e `metadados_fontes`.
- `prep`: `limite_municipal`, `secciones`, `poblacion_seccion`, `grid_250`, `grid_seccion_intersecao`, `gtfs_rotas`,
  `gtfs_servicos_dia`, `gtfs_viagens_dia`, `gtfs_horarios_dia`, `gtfs_paradas`, `tussam_paradas_ide`, `rede_nos`,
  `rede_arestas`, `parametros` e `periodos_analise`. Todos têm chave primária e índice GiST. Todas as geometrias estão em 25830.
- `qa`: `resultado_testes`, `paradas_gtfs_ide` e as views de comparação de limites, sobreposição de seções, distância
  GTFS × IDE e paradas próximas.
- O schema de indicadores ainda não foi criado.

## Decisões deixadas para as próximas etapas

Classificação de densidade, baixa oferta, cobertura em 400 m, linhas acessíveis, frequência por origem, índices
compostos e rankings não foram calculados.
