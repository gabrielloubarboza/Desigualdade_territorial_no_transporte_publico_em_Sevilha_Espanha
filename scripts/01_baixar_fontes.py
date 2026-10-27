"""Etapa 1 — Download das fontes públicas e registro no manifesto (data/manifesto_fontes.json).

Uso:  .venv\\Scripts\\python.exe scripts\\01_baixar_fontes.py [--forcar]

Fontes: GTFS TUSSAM (espelho Mobility Database do feed NAP), seccionado INE 2024, população por
seção (INE Censo Anual), grade IECA 250 m (WFS), paradas/linhas TUSSAM (IDE Sevilla, ArcGIS) e
limite municipal IGN (WFS INSPIRE). A rede OSM é obtida em 03_rede_osm.py.
"""
from __future__ import annotations

import json
import sys
import zipfile

import pyogrio
import requests

from comum import agora_utc, baixar, carregar_config, caminho, hash_arquivo, registrar_fonte, sessao

FORCAR = "--forcar" in sys.argv
CFG = carregar_config()


def extrair(zip_path, destino):
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        ruins = z.testzip()
        if ruins:
            raise RuntimeError(f"Arquivo corrompido no zip: {ruins}")
        z.extractall(destino)
        return [i.filename for i in z.infolist()]


def gtfs():
    c = CFG["gtfs"]
    info = baixar(c["url"], caminho(c["arquivo"]), c["md5_esperado"], FORCAR)
    arquivos = extrair(caminho(c["arquivo"]), caminho("data/raw/gtfs_tussam/extract"))
    # Verificação do link oficial do produtor (NAP): apenas registra o status, sem credenciais.
    try:
        st = sessao().head(c["url_produtor_nap"], timeout=30).status_code
    except requests.RequestException as erro:
        st = f"sem resposta ({type(erro).__name__})"
    registrar_fonte("gtfs_tussam", {
        **info,
        "descricao": "GTFS Schedule TUSSAM (autobuses urbanos + tranvía Metrocentro)",
        "produtor": "Transportes Urbanos de Sevilla S.A.M. (TUSSAM), publicado no Punto de Acceso Nacional (MITRAMS)",
        "url_produtor": c["url_produtor_nap"],
        "status_url_produtor_sem_credencial": st,
        "autenticacao": "NAP exige API key (HTTP 401 sem credencial); espelho Mobility Database é público",
        "catalogo": "https://mobilitydatabase.org/feeds/gtfs/mdb-2770",
        "versao": "mdb-2770-202609300035 (feed_version 20260928)",
        "formato": "GTFS (zip/csv)",
        "licenca": "Licencia de datos abiertos del MITRAMS (https://nap.transportes.gob.es/licencia-datos) — reutilização e redistribuição com atribuição 'Powered by MITRAMS'",
        "arquivos_zip": arquivos,
    })


def ine_seccionado():
    c = CFG["ine_seccionado"]
    info = baixar(c["url"], caminho(c["arquivo"]), forcar=FORCAR)
    arquivos = extrair(caminho(c["arquivo"]), caminho("data/raw/ine_seccionado/extract"))
    registrar_fonte("ine_seccionado_2024", {
        **info,
        "descricao": "Cartografía digitalizada de secciones censales — seccionado a 1 de enero de 2024",
        "produtor": "Instituto Nacional de Estadística (INE)",
        "pagina": "https://www.ine.es/prodyser/cartografia/",
        "versao": "SECC_CE_20240101", "formato": "ESRI Shapefile (EPSG:25830)",
        "licenca": "Aviso legal INE: reutilização permitida citando a fonte (https://www.ine.es/aviso_legal)",
        "autenticacao": "não", "arquivos_zip": arquivos,
    })


def ine_populacao():
    c = CFG["ine_populacao"]
    info = baixar(c["url"], caminho(c["arquivo"]), forcar=FORCAR)
    registrar_fonte("ine_censo_anual_secciones", {
        **info,
        "descricao": "Censo Anual de Población 2021-2025, resultados por secciones censales, provincia de Sevilla — "
                     "Tabela 69258 'Población por sexo y nacionalidad (española/extranjera)'",
        "produtor": "Instituto Nacional de Estadística (INE)",
        "pagina": "https://www.ine.es/dynt3/inebase/es/index.htm?padre=11100&capsel=11143",
        "versao": "publicação de 29/04/2026 (períodos 2021-2025, ref. 1 de janeiro)",
        "formato": "CSV ';' UTF-8 com BOM (HTTP declara ISO-8859-15), separador de milhar '.'",
        "licenca": "Aviso legal INE: reutilização permitida citando a fonte",
        "autenticacao": "não",
    })


def limites_municipio_ine():
    """Bbox do município pelo seccionado INE (para os recortes WFS)."""
    shp = caminho("data/raw/ine_seccionado/extract") / CFG["ine_seccionado"]["shapefile"]
    gdf = pyogrio.read_dataframe(shp, where=f"CUMUN = '{CFG['projeto']['municipio_ine']}'")
    return gdf.total_bounds


def ieca_grid():
    c = CFG["ieca_grid"]
    destino = caminho(c["arquivo"])
    if destino.exists() and not FORCAR:
        print("  grade IECA já presente; use --forcar para obter novamente")
    else:
        x0, y0, x1, y1 = limites_municipio_ine()
        m = c["margem_bbox_m"]
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": c["camada"],
            "outputFormat": "application/json", "srsName": "urn:ogc:def:crs:EPSG::25830",
            "bbox": f"{x0 - m},{y0 - m},{x1 + m},{y1 + m},urn:ogc:def:crs:EPSG::25830",
        }
        r = sessao().get(c["wfs"], params=params, timeout=600)
        r.raise_for_status()
        dados = r.json()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        registrar_fonte("ieca_grid_250m", {"data_obtencao": agora_utc(), "requisicao": r.url,
                                           "n_feicoes": len(dados["features"])})
    registrar_fonte("ieca_grid_250m", {
        "descricao": "Distribución espacial de la población en Andalucía — malla 250 m x 250 m (grid:gridp_250), "
                     "população residente a 1 de enero de 2024",
        "produtor": "Instituto de Estadística y Cartografía de Andalucía (IECA)",
        "pagina": "https://www.juntadeandalucia.es/institutodeestadisticaycartografia/dega/distribucion-espacial-de-la-poblacion-en-andalucia",
        "url": c["wfs"], "arquivo": c["arquivo"], "formato": "GeoJSON via WFS 2.0 (EPSG:25830)",
        "sha256": hash_arquivo(destino), "tamanho_bytes": destino.stat().st_size,
        "licenca": "IECA: produtos sob CC BY 4.0 desde 2014 (citar autoria e data); termos vigentes não "
                   "reconfirmados nesta etapa",
        "autenticacao": "não",
        "documentacao": ["data/raw/ieca_grid/docs/073-distribucion-espacial-poblacion-MT020103.pdf",
                         "data/raw/ieca_grid/docs/073-distribucion-espacial-poblacion-IME020103.pdf"],
    })
    base = ("https://www.juntadeandalucia.es/institutodeestadisticaycartografia/dega/sites/default/files/docs/")
    for doc in ("073-distribucion-espacial-poblacion-MT020103.pdf", "073-distribucion-espacial-poblacion-IME020103.pdf"):
        baixar(base + doc, caminho("data/raw/ieca_grid/docs") / doc, forcar=FORCAR)


def arcgis_camada(url_camada, destino):
    """Baixa todas as feições de uma camada ArcGIS FeatureServer em GeoJSON (EPSG:4326), com paginação."""
    s = sessao()
    meta = s.get(url_camada, params={"f": "json"}, timeout=60).json()
    passo = meta.get("maxRecordCount", 1000)
    feicoes, offset = [], 0
    while True:
        r = s.get(f"{url_camada}/query", params={
            "where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson", "orderByFields": "ObjectId",
            "resultOffset": offset, "resultRecordCount": passo}, timeout=300)
        r.raise_for_status()
        lote = r.json()["features"]
        feicoes += lote
        if len(lote) < passo:
            break
        offset += passo
    total = s.get(f"{url_camada}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
                  timeout=60).json()["count"]
    if total != len(feicoes):
        raise RuntimeError(f"Contagem divergente em {url_camada}: {len(feicoes)} != {total}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"type": "FeatureCollection", "features": feicoes}, ensure_ascii=False),
                       encoding="utf-8")
    edit = meta.get("editingInfo", {}).get("dataLastEditDate")
    return len(feicoes), edit


def tussam_ide():
    c = CFG["tussam_ide"]
    for chave, item in (("paradas", c["item_paradas"]), ("linhas", c["item_linhas"])):
        destino = caminho(c[f"arquivo_{chave}"])
        extra = {}
        if FORCAR or not destino.exists():
            n, edit = arcgis_camada(c[chave], destino)
            extra = {"data_obtencao": agora_utc(), "n_feicoes": n,
                     "data_ultima_edicao_servico_ms": edit}
        try:
            meta = sessao().get(f"https://www.arcgis.com/sharing/rest/content/items/{item}",
                                params={"f": "json"}, timeout=60).json()
            extra.update(descricao=meta.get("snippet"), titulo=meta.get("title"))
        except requests.RequestException as erro:
            print(f"  aviso: metadados do item {item} indisponíveis ({type(erro).__name__})")
        registrar_fonte(f"tussam_ide_{chave}", {
            **extra,
            "produtor": "TUSSAM / Ayuntamiento de Sevilla (IDE Sevilla — cda-idesevilla.opendata.arcgis.com)",
            "url": c[chave], "item_arcgis": item, "arquivo": c[f"arquivo_{chave}"],
            "formato": "GeoJSON (EPSG:4326) exportado de ArcGIS FeatureServer (nativo EPSG:3857)",
            "atualizacao_declarada": "Actualizado a fecha 20/10/2026 (descrição do item)",
            "licenca": "Termos TUSSAM: acesso sem restrição e sem atribuição exigida, mas proíbe redistribuir a "
                       "informação (modificada ou não) em sítio web ou outro meio — NÃO versionar no GitHub",
            "sha256": hash_arquivo(destino), "tamanho_bytes": destino.stat().st_size, "autenticacao": "não",
        })


def ign_limite():
    c = CFG["ign_limite"]
    destino = caminho(c["arquivo"])
    if FORCAR or not destino.exists():
        filtro = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0" '
                  'xmlns:au="http://inspire.ec.europa.eu/schemas/au/4.0"><fes:PropertyIsEqualTo>'
                  '<fes:ValueReference>au:nationalCode</fes:ValueReference>'
                  '<fes:Literal>34014141091</fes:Literal></fes:PropertyIsEqualTo></fes:Filter>')
        r = sessao().get(c["wfs"], params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "au:AdministrativeUnit",
            "srsName": "urn:ogc:def:crs:EPSG::25830", "filter": filtro}, timeout=300)
        r.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        registrar_fonte("ign_limite_municipal", {"data_obtencao": agora_utc()})
    registrar_fonte("ign_limite_municipal", {
        "descricao": "Unidad administrativa municipal de Sevilla (nationalCode 34014141091) — INSPIRE AU",
        "produtor": "Instituto Geográfico Nacional (IGN) / CNIG", "url": c["wfs"], "arquivo": c["arquivo"],
        "formato": "GML 3.2 (EPSG:25830)", "licenca": "CC BY 4.0 (scne.es / ign.es)",
        "sha256": hash_arquivo(destino), "tamanho_bytes": destino.stat().st_size, "autenticacao": "não",
        "uso": "somente comparação com o limite derivado do seccionado INE",
    })


if __name__ == "__main__":
    for etapa in (gtfs, ine_seccionado, ine_populacao, ieca_grid, tussam_ide, ign_limite):
        print(f"[{etapa.__name__}]")
        etapa()
    print("Manifesto atualizado: data/manifesto_fontes.json")
