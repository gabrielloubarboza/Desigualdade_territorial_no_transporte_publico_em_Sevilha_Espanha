"""Verificación en QGIS y estilos por defecto de los GeoPackages finales (Etapa 5).

Se ejecuta con el Python de QGIS (no con el .venv del proyecto), normalmente desde 16_geopackages_finales.py:
    "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\qgis_estilos_geopackages.py <resultados.gpkg> <contexto.gpkg>

Abre cada capa con la API de QGIS, comprueba validez, CRS y número de entidades frente a `metadatos_capas`,
y guarda un estilo por defecto (tabla layer_styles) con la paleta de config/paleta.json.
"""
import json
import os
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsFillSymbol, QgsGraduatedSymbolRenderer,
                       QgsLineSymbol, QgsMarkerSymbol, QgsPalLayerSettings, QgsRendererCategory, QgsRendererRange,
                       QgsTextFormat, QgsVectorLayer, QgsVectorLayerSimpleLabeling)
from qgis.PyQt.QtGui import QColor

PALETA = json.loads((Path(__file__).resolve().parents[1] / "config" / "paleta.json").read_text(encoding="utf-8"))
TINTA = PALETA["tinta"]


def poligono(color, borde="#FFFFFF", ancho="0.15"):
    return QgsFillSymbol.createSimple({"color": color, "outline_color": borde, "outline_width": ancho})


def categorizado(campo, cats, simbolo):
    return QgsCategorizedSymbolRenderer(campo, [QgsRendererCategory(v, simbolo(c), etq) for v, c, etq in cats])


def graduado(campo, rangos, colores, simbolo):
    r = [QgsRendererRange(a, b, simbolo(c), etq) for (a, b, etq), c in zip(rangos, colores)]
    return QgsGraduatedSymbolRenderer(campo, r)


def etiquetas(capa, expresion, tam=8):
    s = QgsPalLayerSettings()
    s.fieldName = expresion
    s.isExpression = True
    f = QgsTextFormat()
    f.setSize(tam)
    f.setColor(QColor(TINTA))
    s.setFormat(f)
    capa.setLabeling(QgsVectorLayerSimpleLabeling(s))
    capa.setLabelsEnabled(True)


def estilo(nombre, capa):
    tip = PALETA["tipologia"]
    cats_tip = [(k, v, PALETA["tipologia_etiqueta"][k]) for k, v in tip.items()]
    if nombre in ("secciones_indicadores", "secciones_prioritarias"):
        capa.setRenderer(categorizado("tipologia", cats_tip, lambda c: poligono(c)))
        if nombre == "secciones_prioritarias":
            etiquetas(capa, "\"ranking\"")
        return "Tipología A–D"
    if nombre == "distritos":
        capa.renderer().setSymbol(QgsFillSymbol.createSimple({"style": "no", "outline_color": TINTA, "outline_width": "0.5"}))
        etiquetas(capa, "\"cdis\" || ' ' || \"nombre\"", 9)
        return "Contorno de distritos"
    if nombre == "limite_municipal":
        capa.renderer().setSymbol(QgsFillSymbol.createSimple({"style": "no", "outline_color": TINTA, "outline_width": "0.8"}))
        return "Contorno municipal"
    if nombre == "celdas_ieca_250m":
        rangos = [(0, 100, "≤ 100"), (100, 500, "100–500"), (500, 1000, "500–1.000"), (1000, 1500, "1.000–1.500"),
                  (1500, 2000, "1.500–2.000"), (2000, 1e9, "> 2.000")]
        capa.setRenderer(graduado("pob_tot", rangos, PALETA["densidad"], lambda c: poligono(c, "#FFFFFF", "0.05")))
        return "Población por celda (pob_tot)"
    if nombre == "puntos_demanda":
        cats = [("coberto_400m", PALETA["servicio"][4], "Con parada a ≤ 400 m"),
                ("sem_cobertura_400m", PALETA["sin_cobertura"][4], "Sin parada a ≤ 400 m"),
                ("nao_determinado", "#9AA3AB", "No determinado")]
        capa.setRenderer(categorizado("situacion_400m", cats, lambda c: QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": c, "outline_color": "#FFFFFF", "size": "1.6"})))
        return "Situación a 400 m"
    if nombre == "paradas_autobus":
        rangos = [(0, 0.01, "0"), (0.01, 10, "≤ 10"), (10, 30, "10–30"), (30, 60, "30–60"), (60, 1e9, "> 60")]
        capa.setRenderer(graduado("salidas_h_manana", rangos, PALETA["servicio"][1:], lambda c: QgsMarkerSymbol.createSimple(
            {"name": "circle", "color": c, "outline_color": TINTA, "outline_width": "0.1", "size": "1.8"})))
        return "Salidas/h 07–09"
    if nombre == "red_peatonal":
        cats = [(1, "#9AA3AB", "Utilizable"), (0, "#C8323F", "Excluida (motivo_exclusion)")]   # booleano en GPKG = 0/1
        capa.setRenderer(categorizado("utilizable", cats, lambda c: QgsLineSymbol.createSimple({"color": c, "width": "0.2"})))
        return "Red peatonal"
    if nombre in ("barreras_poligonos", "barreras_lineas"):
        cats = [("agua", PALETA["agua"], "Agua"), ("curso_agua", "#7FA9C2", "Curso de agua"),
                ("ferrovia", "#5B6670", "Ferrocarril"), ("via_alta_capacidade", "#B4532A", "Vía de gran capacidad")]
        capa.setRenderer(QgsCategorizedSymbolRenderer("clase", [
            QgsRendererCategory(v, (poligono(c, c) if capa.geometryType() == 2 else QgsLineSymbol.createSimple({"color": c, "width": "0.5"})), e)
            for v, c, e in cats]))
        return "Barreras por clase"
    return None


def main(rutas):
    app = QgsApplication([], False)
    app.initQgis()
    errores = 0
    for ruta in rutas:
        meta = QgsVectorLayer(f"{ruta}|layername=metadatos_capas", "meta", "ogr")
        esperado = {f["capa"]: f["n_registros"] for f in meta.getFeatures()}
        for capa_nombre, n in esperado.items():
            capa = QgsVectorLayer(f"{ruta}|layername={capa_nombre}", capa_nombre, "ogr")
            ok = capa.isValid() and capa.featureCount() == n and capa.crs().authid() == "EPSG:25830"
            if not ok:
                errores += 1
            desc = estilo(capa_nombre, capa) if ok else None
            if desc:
                capa.saveStyleToDatabase(capa_nombre, desc, True, "")
            print(f"  QGIS {Path(ruta).name}:{capa_nombre}: válida={capa.isValid()} entidades={capa.featureCount()}/{n} "
                  f"crs={capa.crs().authid()} estilo={'sí' if desc else 'no'}")
    # exitQgis() provoca un access violation en Windows con capas aún en memoria; se sale directamente
    sys.stdout.flush()
    os._exit(1 if errores else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
