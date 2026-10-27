"""Proyecto QGIS con los mapas del informe (Etapa 5). Se ejecuta con el Python de QGIS desde 22_proyecto_qgis.py:
    "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat" scripts\\qgis_proyecto_layouts.py <geometria.json> <proyecto.qgz> [<carpeta_png>]

Solo usa archivos del proyecto: los GeoPackages de produtos/ (rutas relativas en el .qgz), config/paleta.json y las
fuentes de assets/fonts. El JSON trae la geometría de cada figura medida en matplotlib (página, mapas, leyendas,
textos, escala y norte, clases); cada mapa se reconstruye como diseño de impresión con las mismas medidas, y cada
figura tiene su grupo de capas y su tema de mapa. Unidades: milímetros en el diseño, puntos en símbolos y textos.
"""
import json
import os
import sys
from pathlib import Path

from qgis.core import (Qgis, QgsApplication, QgsCallout, QgsCategorizedSymbolRenderer, QgsCoordinateReferenceSystem,
                       QgsFeatureRequest, QgsFillSymbol, QgsLayerTreeLayer, QgsLayoutExporter, QgsLayoutItem,
                       QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap, QgsLayoutItemPolygon, QgsLayoutMeasurement,
                       QgsLayoutPoint, QgsLayoutSize, QgsLegendRenderer, QgsLegendStyle, QgsLineSymbol,
                       QgsMapLayerLegendUtils, QgsMapThemeCollection, QgsMarkerSymbol, QgsPalLayerSettings, QgsPrintLayout,
                       QgsProject, QgsProperty, QgsRectangle, QgsReferencedRectangle, QgsRenderContext, QgsRendererCategory,
                       QgsRuleBasedRenderer, QgsSimpleLineCallout, QgsSingleSymbolRenderer, QgsTextBackgroundSettings,
                       QgsTextFormat, QgsTextRenderer, QgsVectorLayer, QgsVectorLayerSimpleLabeling,
                       QgsGeometryGeneratorSymbolLayer)
from qgis.PyQt.QtCore import QPointF, QRectF, QSizeF, Qt
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase, QPolygonF

RAIZ = Path(__file__).resolve().parents[1]
RES = RAIZ / "produtos" / "sevilla_oferta_bus_resultados.gpkg"
CTX = RAIZ / "produtos" / "sevilla_oferta_bus_contexto_osm.gpkg"
PT = Qgis.RenderUnit.Points
PT_MM = 25.4 / 72
FUENTE = "IBM Plex Sans"
PROP = getattr(QgsPalLayerSettings, "Property", QgsPalLayerSettings)
TITULOS = {"portada.png": "00 · Portada", "mapa_localizacion.png": "01 · Área de estudio (pág. 2)",
           "mapa_densidad.png": "02 · Densidad de población (pág. 3)", "mapa_cobertura.png": "03 · Población sin parada a 400 m (pág. 4)",
           "mapa_lineas.png": "04 · Líneas accesibles 07–09 (pág. 5)", "mapa_frecuencia.png": "05 · Salidas/h accesibles 07–09 (pág. 6)",
           "mapa_variacion.png": "06 · Variación tarde frente a mañana (pág. 7)", "mapa_prioritarias.png": "07 · Secciones prioritarias (pág. 10)",
           "mapa_detalle.png": "08 · Detalle de las prioritarias (pág. 11)"}
CAMPO = {"mapa_densidad.png": "densidade_ine_hab_km2", "mapa_cobertura.png": "pct_sem_cobertura_400m",
         "mapa_lineas.png": "linhas_cob_manha", "mapa_frecuencia.png": "partidas_h_cob_manha",
         "mapa_variacion.png": "var_pct_tarde_manha"}


# ------------------------------------------------------------------ símbolos y textos
def n(x):
    return f"{float(x):.10f}".rstrip("0").rstrip(".")


def relleno(color=None, borde=None, ancho=0.0, opacidad=1.0):
    s = QgsFillSymbol.createSimple({"color": color or "0,0,0,0", "style": "solid" if color else "no",
                                    "outline_color": borde or "0,0,0,0", "outline_style": "solid" if borde and ancho else "no",
                                    "outline_width": str(ancho), "outline_width_unit": "Point", "joinstyle": "round"})
    s.setOpacity(opacidad)
    return s


def linea(color, ancho):
    return QgsLineSymbol.createSimple({"line_color": color, "line_width": str(ancho), "line_width_unit": "Point",
                                       "joinstyle": "round", "capstyle": "square"})


def marcador(forma, color, borde=None, ancho_borde=0.0, tam=1.0, opacidad=1.0, tam_expr=None):
    s = QgsMarkerSymbol.createSimple({"name": forma, "color": color, "outline_color": borde or "0,0,0,0",
                                      "outline_style": "solid" if borde else "no", "outline_width": str(ancho_borde),
                                      "outline_width_unit": "Point", "size": str(tam), "size_unit": "Point"})
    s.setOpacity(opacidad)
    if tam_expr:
        s.setDataDefinedSize(QgsProperty.fromExpression(tam_expr))
    return s


def estilo_fuente(weight, style="normal"):
    if isinstance(weight, (int, float)):
        weight = "bold" if weight >= 700 else "semibold" if weight >= 600 else "medium" if weight >= 500 else "normal"
    if style == "italic":
        return "Italic"
    return {"semibold": "SemiBold", "demibold": "SemiBold", "demi": "SemiBold", "bold": "Bold", "heavy": "Bold",
            "medium": "Medium"}.get(str(weight), "Regular")


def formato(size, weight="normal", style="normal", color="#1D2A35", interlineado_pt=None):
    f = QgsTextFormat()
    f.setFont(QFont(FUENTE))
    f.setNamedStyle(estilo_fuente(weight, style))
    f.setSize(size)
    f.setSizeUnit(PT)
    f.setColor(QColor(color))
    if interlineado_pt:   # distancia entre líneas medida en matplotlib
        f.setLineHeight(interlineado_pt)
        f.setLineHeightUnit(PT)
    return f


def fondo_texto(f, fondo, size):
    """Caja de matplotlib (round/circle, pad en fracción del cuerpo) como fondo de etiqueta."""
    b = QgsTextBackgroundSettings()
    b.setEnabled(True)
    circulo = fondo["estilo"] == "circle"
    b.setType(QgsTextBackgroundSettings.ShapeCircle if circulo else QgsTextBackgroundSettings.ShapeRectangle)
    pad = fondo["pad"] * size
    if circulo:   # tamaño fijo por etiqueta (definido por datos en rotulos)
        b.setSizeType(QgsTextBackgroundSettings.SizeFixed)
        b.setSize(QSizeF(3, 3))
        b.setSizeUnit(Qgis.RenderUnit.Millimeters)
    else:
        b.setSizeType(QgsTextBackgroundSettings.SizeBuffer)
        b.setSize(QSizeF(pad, pad))
        b.setSizeUnit(PT)
    if not circulo:
        b.setRadii(QSizeF(pad, pad))
        b.setRadiiUnit(PT)
    b.setFillColor(QColor(fondo["fc"]))
    b.setOpacity(fondo["alpha"])
    if fondo["ec"]:
        b.setStrokeColor(QColor(fondo["ec"]))
        b.setStrokeWidth(fondo["lw"])
        b.setStrokeWidthUnit(PT)
    else:
        b.setStrokeColor(QColor(0, 0, 0, 0))
        b.setStrokeWidth(0)
    f.setBackground(b)
    return f


def rotulos(capa, texto, campo_clave, posiciones, t, callout=False):
    """Etiquetas de capa colocadas en la posición medida en la figura (centro del texto en coordenadas del mapa)."""
    s = QgsPalLayerSettings()
    s.fieldName = texto
    s.isExpression = True
    f = formato(t["size"], t["weight"], t["style"], t["color"], t.get("salto_pt"))
    if t.get("fondo"):
        fondo_texto(f, t["fondo"], t["size"])
    s.setFormat(f)
    s.placement = Qgis.LabelPlacement.OverPoint
    s.multilineAlignment = Qgis.LabelMultiLineAlignment.Center
    s.priority = 10
    s.displayAll = True
    s.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapAtNoCost)
    s.placementSettings().setAllowDegradedPlacement(True)
    s.obstacleSettings().setIsObstacle(False)
    dd = s.dataDefinedProperties()
    for prop, eje in ((PROP.PositionX, 0), (PROP.PositionY, 1)):
        casos = " ".join(f"WHEN {campo_clave} = {k} THEN {n(p['centro_datos'][eje])}" for k, p in posiciones.items())
        dd.setProperty(prop, QgsProperty.fromExpression(f"CASE {casos} END"))
    if t.get("fondo", {}).get("estilo") == "circle":
        # matplotlib: diámetro = lado mayor del texto + 2·pad (QGIS circunscribiría el rectángulo del texto)
        pad = t["fondo"]["pad"] * t["size"] * PT_MM
        casos = " ".join(f"WHEN {campo_clave} = {k} THEN {n(max(p['ancho'], p['alto']) + 2 * pad)}" for k, p in posiciones.items())
        for prop in (PROP.ShapeSizeX, PROP.ShapeSizeY):
            dd.setProperty(prop, QgsProperty.fromExpression(f"CASE {casos} END"))
    dd.setProperty(PROP.Hali, QgsProperty.fromValue("Center"))
    dd.setProperty(PROP.Vali, QgsProperty.fromValue("Half"))
    s.setDataDefinedProperties(dd)
    if callout:
        c = QgsSimpleLineCallout()
        c.setEnabled(True)
        c.setLineSymbol(linea(t["fondo"]["ec"], t["fondo"]["lw"]))
        c.setAnchorPoint(QgsCallout.PointOnSurface)
        c.setLabelAnchorPoint(QgsCallout.LabelPointOnExterior)
        c.setMinimumLength(0)
        s.setCallout(c)
    capa.setLabeling(QgsVectorLayerSimpleLabeling(s))
    capa.setLabelsEnabled(True)


# ------------------------------------------------------------------ proyecto
class Proyecto:
    def __init__(self, geo):
        self.p = QgsProject.instance()
        self.p.clear()
        self.p.setCrs(QgsCoordinateReferenceSystem("EPSG:25830"))
        self.p.setTitle("Desigualdad territorial en la oferta de autobuses urbanos de Sevilla")
        self.p.setFilePathStorage(Qgis.FilePathType.Relative)
        self.geo = geo
        self.pal = geo["paleta"]
        self.tinta = self.pal["tinta"]
        self.raiz = self.p.layerTreeRoot()

    def capa(self, grupo, gpkg, nombre, titulo, filtro=None):
        c = QgsVectorLayer(f"{gpkg}|layername={nombre}", titulo, "ogr")
        if not c.isValid():
            raise RuntimeError(f"Capa no válida: {gpkg.name}:{nombre}")
        if filtro:
            c.setSubsetString(filtro)
        if grupo is not None:   # capas de los mapas: sin el etiquetado por defecto
            c.setLabelsEnabled(False)
            c.setLabeling(None)
        self.p.addMapLayer(c, False)
        (grupo or self.raiz).insertLayer(0, c)   # la última añadida queda encima
        return c

    def grupo(self, nombre, visible=False):
        g = self.raiz.addGroup(nombre)
        g.setItemVisibilityChecked(visible)
        g.setExpanded(False)
        return g

    def tema(self, nombre, capas):
        rec = QgsMapThemeCollection.MapThemeRecord()
        rec.setLayerRecords([QgsMapThemeCollection.MapThemeLayerRecord(c) for c in capas])
        self.p.mapThemeCollection().insert(nombre, rec)

    # capas de contexto comunes a varios mapas (mismo orden de dibujo que visual.mapa_base)
    def agua(self, g, color=None):
        c = self.capa(g, CTX, "barreras_poligonos", "Agua (OSM)", "\"clase\" = 'agua'")
        c.setRenderer(QgsSingleSymbolRenderer(relleno(color or self.pal["agua"])))
        return c

    def distritos(self, g):
        c = self.capa(g, RES, "distritos", "Distritos censales")
        c.setRenderer(QgsSingleSymbolRenderer(relleno(None, self.tinta, 0.55)))
        return c

    def limite(self, g, color=None, ancho=0.9):
        c = self.capa(g, RES, "limite_municipal", "Límite municipal")
        c.setRenderer(QgsSingleSymbolRenderer(relleno(None, color or self.tinta, ancho)))
        return c

    def reglas(self, capa, campo, clase, items):
        """Clases [c_i, c_i+1) como visual.clasificar; fuera de rango = último color; NULL = gris de la figura."""
        raiz = QgsRuleBasedRenderer.Rule(None)
        cortes, colores = clase["cortes"], clase["colores"]
        k = len(colores)
        for i in range(k):
            if i < k - 1:
                expr = f'"{campo}" >= {n(cortes[i])} AND "{campo}" < {n(cortes[i + 1])}'
            else:
                expr = f'"{campo}" >= {n(cortes[i])} OR "{campo}" < {n(cortes[0])}'
            raiz.appendChild(QgsRuleBasedRenderer.Rule(relleno(colores[i], "#FFFFFF", 0.12), 0, 0, expr, items[i][1]))
        nulos = capa.featureCount() - sum(1 for _ in capa.getFeatures(QgsFeatureRequest().setFilterExpression(f'"{campo}" IS NOT NULL')))
        if len(items) > k:
            raiz.appendChild(QgsRuleBasedRenderer.Rule(relleno(items[k][0], "#FFFFFF", 0.12), 0, 0, f'"{campo}" IS NULL', items[k][1]))
        elif nulos:
            raise RuntimeError(f"{campo}: {nulos} nulos sin clase en la leyenda de la figura")
        capa.setRenderer(QgsRuleBasedRenderer(raiz))

    # ------------------------------------------------------------------ capas por figura
    def capas_figura(self, fig):
        nombre = fig["nombre"]
        g = self.grupo(TITULOS[nombre])
        pal, tinta = self.pal, self.tinta
        datos = [t for e in fig["ejes"] for t in e["textos"] if t["tipo"] == "datos"]
        temas = {}
        if nombre == "portada.png":
            a = self.agua(g, "#24394A")
            r = self.capa(g, CTX, "red_peatonal", "Red peatonal utilizable", '"utilizable" = 1')
            r.setRenderer(QgsSingleSymbolRenderer(linea("#3E5466", 0.18)))
            pr = self.capa(g, RES, "secciones_indicadores", "Secciones prioritarias", '"prioritaria" = 1')
            pr.setRenderer(QgsSingleSymbolRenderer(relleno("#F2F0EA")))
            pa = self.capa(g, RES, "paradas_autobus", "Paradas con salidas 07–09", '"salidas_h_manana" > 0')
            pa.setRenderer(QgsSingleSymbolRenderer(marcador("circle", "#8FBDD8", tam=1, opacidad=0.85,
                                                            tam_expr='sqrt(1.2 + "salidas_h_manana" / 6)')))
            li = self.limite(g, "#8A99A6", 0.6)
            temas[0] = [a, r, pr, pa, li]
        elif nombre == "mapa_localizacion.png":
            s = self.capa(g, RES, "secciones_indicadores", "Secciones censales")
            s.setRenderer(QgsSingleSymbolRenderer(relleno("#F4F2EE", "#B9BEC4", 0.15)))
            a = self.agua(g)
            d = self.distritos(g)
            rotulos(d, "\"cdis\" || '\\n' || \"nombre\"", '"cdis"', {f"'{t['texto'][:2]}'": t for t in datos}, datos[0])
            li = self.limite(g)
            c = self.capa(g, RES, "contexto_ccaa", "Comunidades autónomas")
            c.setRenderer(QgsSingleSymbolRenderer(relleno("#E7E5DF", "#FFFFFF", 0.3)))
            an = self.capa(g, RES, "contexto_ccaa", "Andalucía", "\"cca\" = '01'")
            an.setRenderer(QgsSingleSymbolRenderer(relleno("#BDA3D0", "#FFFFFF", 0.3)))
            ce = self.capa(g, RES, "limite_municipal", "Sevilla (centroide)")
            gen = QgsGeometryGeneratorSymbolLayer.create({"geometryModifier": "centroid($geometry)", "SymbolType": "Marker"})
            gen.setSubSymbol(marcador("circle", tinta, tinta, 1.0, 3.5))
            sym = relleno()
            sym.changeSymbolLayer(0, gen)
            ce.setRenderer(QgsSingleSymbolRenderer(sym))
            temas[0], temas[1] = [s, a, d, li], [c, an, ce]
        elif nombre in CAMPO:
            s = self.capa(g, RES, "secciones_indicadores", "Secciones censales")
            self.reglas(s, CAMPO[nombre], fig["clases"][0], fig["leyendas"][0]["items"])
            a = self.agua(g)
            d = self.distritos(g)
            rotulos(d, '"cdis"', '"cdis"', {f"'{t['texto']}'": t for t in datos}, datos[0])
            temas[0] = [s, a, d, self.limite(g)]
            self.leyenda_capa = s
        elif nombre == "mapa_prioritarias.png":
            items = fig["leyendas"][0]["items"]
            s = self.capa(g, RES, "secciones_indicadores", "Secciones censales (tipología)")
            s.setRenderer(QgsCategorizedSymbolRenderer("tipologia", [
                QgsRendererCategory(t, relleno(c, "#FFFFFF", 0.12), e) for t, (c, e) in zip(self.geo["tip_orden"], items)]))
            a = self.agua(g)
            d = self.distritos(g)
            rotulos(d, '"cdis"', '"cdis"', {f"'{t['texto']}'": t for t in datos}, datos[0])
            li = self.limite(g)
            pr = self.capa(g, RES, "secciones_indicadores", "Secciones prioritarias (contorno)", '"prioritaria" = 1')
            pr.setRenderer(QgsCategorizedSymbolRenderer("tipologia", [
                QgsRendererCategory(t, relleno(None, pal["tipologia"][t], 1.6), pal["tipologia_etiqueta"][t]) for t in self.geo["tip_orden"][:4]]))
            anot = [t for t in fig["ejes"][0]["textos"] if t["tipo"] == "anotacion"]
            claves = ", ".join(t["texto"] for t in anot)
            rotulos(pr, f'CASE WHEN "ranking" IN ({claves}) THEN to_string("ranking") END', '"ranking"',
                    {t["texto"]: t for t in anot}, anot[0], callout=True)
            temas[0] = [s, a, d, li, pr]
            self.leyenda_capa = s
        elif nombre == "mapa_detalle.png":
            s = self.capa(g, RES, "secciones_indicadores", "Secciones censales")
            s.setRenderer(QgsSingleSymbolRenderer(relleno("#FFFFFF", "#B9BEC4", 0.3)))
            sp = self.capa(g, RES, "secciones_indicadores", "Secciones prioritarias (tinte)", '"prioritaria" = 1')
            sp.setRenderer(QgsCategorizedSymbolRenderer("tipologia", [
                QgsRendererCategory(t, relleno(pal["tipologia"][t], opacidad=0.18), pal["tipologia_etiqueta"][t]) for t in self.geo["tip_orden"][:4]]))
            ley = fig["leyendas_figura"][0]["items"]
            r = self.capa(g, CTX, "red_peatonal", ley[3], '"utilizable" = 1')
            r.setRenderer(QgsSingleSymbolRenderer(linea("#C9CED3", 0.35)))
            a = self.agua(g)
            focos = []
            for i, (tit, cod) in enumerate(self.geo["zonas_detalle"]):
                f = self.capa(g, RES, "secciones_indicadores", f"Panel {i + 1}: {tit}",
                              '"cusec" IN (' + ", ".join(f"'{c}'" for c in cod) + ")")
                f.setRenderer(QgsCategorizedSymbolRenderer("tipologia", [
                    QgsRendererCategory(t, relleno(None, pal["tipologia"][t], 1.4), pal["tipologia_etiqueta"][t]) for t in self.geo["tip_orden"][:4]]))
                tx = [t for t in fig["ejes"][i]["textos"] if t["tipo"] == "datos"]
                rotulos(f, f'CASE WHEN "ranking" IN ({", ".join(t["texto"] for t in tx)}) THEN to_string("ranking") END',
                        '"ranking"', {t["texto"]: t for t in tx}, tx[0])
                focos.append(f)
            pt = self.capa(g, RES, "puntos_demanda", "Puntos de demanda")
            cats = [("coberto_400m", pal["servicio"][4], ley[0]), ("sem_cobertura_400m", pal["tipologia"]["A_baixa_cobertura"], ley[1]),
                    ("nao_determinado", "#9AA3AB", "Punto no determinado")]
            pt.setRenderer(QgsCategorizedSymbolRenderer("situacion_400m", [
                QgsRendererCategory(v, marcador("circle", c, "#FFFFFF", 0.4, 5, 0.9, 'sqrt(3 + "pob_estimada" / 40)'), e)
                for v, c, e in cats]))   # scatter: s en pt², diámetro sqrt(s)
            pa = self.capa(g, RES, "paradas_autobus", ley[2])
            pa.setRenderer(QgsSingleSymbolRenderer(marcador("square", "#FFFFFF", tinta, 0.7, 5,
                                                            tam_expr='sqrt(5 + "salidas_h_manana" * 0.7)')))
            temas[0] = [s, sp, r, a, focos[0], pt, pa]
            temas[1] = [s, sp, r, a, focos[1], pt, pa]
            self.leyenda_capas = (pt, pa, r)
            # símbolos de la leyenda de matplotlib (Line2D: marcador de 5 pt con borde de 1 pt del mismo color)
            self.simbolos_leyenda = {pt.id(): {0: marcador("circle", cats[0][1], cats[0][1], 1.0, 5),
                                               1: marcador("circle", cats[1][1], cats[1][1], 1.0, 5)},
                                     pa.id(): {0: marcador("square", "#FFFFFF", tinta, 1.0, 5)},
                                     r.id(): {0: linea("#C9CED3", 1.2)}}
        nombres = {}
        for i, capas in temas.items():
            if len(temas) == 1:
                suf = ""
            elif nombre == "mapa_localizacion.png":
                suf = " — principal" if i == 0 else " — situación"
            else:
                suf = f" — panel {i + 1}"
            nombres[i] = TITULOS[nombre] + suf
            self.tema(nombres[i], capas)
        return nombres


# ------------------------------------------------------------------ diseños de impresión
def etiqueta(l, t, nombre):
    lab = QgsLayoutItemLabel(l)
    lab.setId(nombre)
    lab.setText(t["texto"])
    lab.setTextFormat(formato(t["size"], t["weight"], t["style"], t["color"]))
    lab.setMarginX(0)
    lab.setMarginY(0)
    x, y, w, h = t["caja"]
    cx, cy = x + w / 2, y + h / 2
    ancho, alto = t["ancho"] + 3, t["alto"]
    ha = {"left": Qt.AlignLeft, "right": Qt.AlignRight}.get(t["ha"], Qt.AlignHCenter)
    lab.setHAlign(ha)
    lab.setVAlign(Qt.AlignVCenter)
    if t["rot"]:
        x0 = cx - ancho / 2
    else:
        x0 = x if ha == Qt.AlignLeft else x + w - ancho if ha == Qt.AlignRight else cx - ancho / 2
    l.addLayoutItem(lab)
    lab.attemptSetSceneRect(QRectF(x0, cy - alto / 2, ancho, alto))
    if t["rot"]:
        lab.setItemRotation(-t["rot"], True)
    return lab


def mapa(l, eje, tema, nombre, crs):
    m = QgsLayoutItemMap(l)
    m.setId(nombre)
    l.addLayoutItem(m)
    x, y, w, h = eje["caja"]
    m.attemptSetSceneRect(QRectF(x, y, w, h))
    m.setCrs(crs)
    m.setExtent(QgsRectangle(eje["xlim"][0], eje["ylim"][0], eje["xlim"][1], eje["ylim"][1]))
    m.setFollowVisibilityPreset(True)
    m.setFollowVisibilityPresetName(tema)
    m.setBackgroundEnabled(False)
    m.setLabelMargin(QgsLayoutMeasurement(0))
    m.setMapFlags(QgsLayoutItemMap.ShowPartialLabels)
    if eje["eje_visible"]:
        m.setFrameEnabled(True)
        m.setFrameStrokeColor(QColor(eje["marco"]))
        m.setFrameStrokeWidth(QgsLayoutMeasurement(eje["marco_lw"] * PT_MM))
    else:
        m.setFrameEnabled(False)
    return m


def escala_norte(l, eje, k):
    items = []
    for j, p in enumerate(eje["escala"]):
        pol = QgsLayoutItemPolygon(QPolygonF([QPointF(x, y) for x, y in p["vertices"]]), l)
        pol.setSymbol(relleno(p["fc"], p["ec"], p["lw"]))
        pol.setId(f"escala_{k}_{j}" if j < len(eje["escala"]) - 1 else f"norte_{k}")
        l.addLayoutItem(pol)
        items.append(pol)
    for j, t in enumerate(x for x in eje["textos"] if x["tipo"] == "escala"):
        items.append(etiqueta(l, t, f"escala_texto_{k}_{j}"))
    return items


def alto_texto(f):
    """Alto de una línea de texto en mm, como lo mide el motor de texto de QGIS."""
    ctx = QgsRenderContext()
    ctx.setScaleFactor(1.0)   # 1 unidad de pintor = 1 mm
    return QgsTextRenderer.textHeight(ctx, f, ["Xg"], Qgis.TextLayoutMode.Rectangle)


def leyenda(l, m, capas, titulo, med, fs, ref, ncol=1, sym=(1.3, 0.9), labelspacing=0.35, orden=None, simbolos=None):
    """Leyenda con las medidas de matplotlib: mismo tamaño de símbolo, paso entre filas y posición de la esquina."""
    em = fs * PT_MM
    paso_sym = (med["paso"] - sym[1] * em) if med.get("paso") else labelspacing * em
    sep_tit = labelspacing * em
    if med.get("sep_titulo") and titulo:
        sep_tit = max(0.0, med["sep_titulo"] - alto_texto(formato(fs + 0.4, "semibold")) / 2 - paso_sym - sym[1] * em / 2)
    caja = med["caja"]
    lg = QgsLayoutItemLegend(l)
    lg.setId("leyenda")
    l.addLayoutItem(lg)
    lg.setLinkedMap(m)
    lg.setAutoUpdateModel(False)
    raiz = lg.model().rootGroup()
    raiz.clear()
    for c, (texto_capa) in capas:
        nodo = raiz.addLayer(c)
        if texto_capa is None:
            QgsLegendRenderer.setNodeLegendStyle(nodo, QgsLegendStyle.Hidden)
        else:
            nodo.setCustomProperty("legend/title-label", texto_capa)
        if orden and c.id() in orden:
            QgsMapLayerLegendUtils.setLegendNodeOrder(nodo, orden[c.id()])
        for i, sim in (simbolos or {}).get(c.id(), {}).items():
            QgsMapLayerLegendUtils.setLegendNodeCustomSymbol(nodo, i, sim)
        lg.model().refreshLayerLegend(nodo)
    lg.setTitle(titulo or "")
    lg.setTitleAlignment(Qt.AlignLeft)
    for comp, f, margenes in ((QgsLegendStyle.Title, formato(fs + 0.4, "semibold"), {QgsLegendStyle.Bottom: sep_tit}),
                              (QgsLegendStyle.SymbolLabel, formato(fs), {QgsLegendStyle.Left: 0.8 * em, QgsLegendStyle.Top: 0}),
                              (QgsLegendStyle.Symbol, None, {QgsLegendStyle.Top: paso_sym}),
                              (QgsLegendStyle.Group, formato(fs), {QgsLegendStyle.Top: 0}),
                              (QgsLegendStyle.Subgroup, formato(fs), {QgsLegendStyle.Top: 0})):
        st = lg.style(comp)
        if f is not None:
            st.setTextFormat(f)
        for lado, v in margenes.items():
            st.setMargin(lado, v)
        lg.setStyle(comp, st)
    lg.setSymbolWidth(sym[0] * em)
    lg.setSymbolHeight(sym[1] * em)
    lg.setBoxSpace(0.4 * em)
    lg.setColumnSpace(2.0 * em)
    lg.setColumnCount(ncol)
    lg.setSplitLayer(True)
    lg.setBackgroundEnabled(False)
    lg.setFrameEnabled(False)
    lg.setResizeToContents(True)
    lg.adjustBoxSize()
    x, y, w, h = caja
    lg.setReferencePoint(ref)
    if ref == QgsLayoutItem.LowerRight:
        lg.attemptMove(QgsLayoutPoint(x + w, y + h))
    else:
        lg.attemptMove(QgsLayoutPoint(x + w / 2, y + h))
    return lg


def disenos(pr, temas):
    crs = QgsCoordinateReferenceSystem("EPSG:25830")
    out = []
    for fig in pr.geo["figuras"]:
        nombre = fig["nombre"]
        l = QgsPrintLayout(pr.p)
        l.initializeDefaults()
        l.setName(nombre.replace(".png", ""))
        pc = l.pageCollection()
        pc.page(0).setPageSize(QgsLayoutSize(*fig["pagina"]))
        pc.setPageStyleSymbol(relleno(fig["fondo"]))
        mapas = []
        for k, eje in enumerate(fig["ejes"]):
            m = mapa(l, eje, temas[nombre][k], "mapa" if k == 0 else f"mapa_{k + 1}", crs)
            mapas.append(m)
            if eje["escala"]:
                l.groupItems(escala_norte(l, eje, k + 1)).setId(f"escala_y_norte_{k + 1}")
            for j, t in enumerate(t for t in eje["textos"] if t["tipo"] in ("ejes", "titulo")):
                etiqueta(l, t, f"{t['tipo']}_{k + 1}_{j + 1}")
        if fig["leyendas"]:
            lg = fig["leyendas"][0]
            leyenda(l, mapas[0], [(pr.leyendas[nombre], None)], lg["titulo"], fig["ejes"][0]["leyenda"], 6.6, QgsLayoutItem.LowerRight)
        if fig["leyendas_figura"]:
            pt, pa, r = pr.leyenda_capas
            leyenda(l, mapas[0], [(pt, None), (pa, fig["leyendas_figura"][0]["items"][2]), (r, fig["leyendas_figura"][0]["items"][3])],
                    None, fig["leyendas_figura"][0], 6.4, QgsLayoutItem.LowerMiddle, ncol=4, sym=(2.0, 0.7),
                    labelspacing=0.5, orden={pt.id(): [0, 1]}, simbolos=pr.simbolos_leyenda)
        pr.p.layoutManager().addLayout(l)
        out.append(l)
    return out


def main(json_path, salida, carpeta_png=None):
    app = QgsApplication([], False)
    app.initQgis()
    for f in sorted((RAIZ / "assets" / "fonts").glob("*.ttf")):   # para exportar; en QGIS hay que instalarlas
        QFontDatabase.addApplicationFont(str(f))
    geo = json.loads(Path(json_path).read_text(encoding="utf-8"))
    pr = Proyecto(geo)
    pr.leyendas = {}
    # 1) GeoPackages completos con su estilo por defecto (tabla layer_styles)
    base = pr.grupo("GeoPackages (estilos por defecto)", visible=True)
    for gpkg, capas in ((CTX, ["red_peatonal", "barreras_lineas", "barreras_poligonos"]),
                        (RES, ["contexto_ccaa", "celdas_ieca_250m", "secciones_indicadores", "secciones_prioritarias",
                               "distritos", "limite_municipal", "puntos_demanda", "paradas_autobus"])):
        for c in capas:
            capa = QgsVectorLayer(f"{gpkg}|layername={c}", c, "ogr")
            if not capa.isValid():
                raise RuntimeError(f"Capa no válida: {c}")
            pr.p.addMapLayer(capa, False)
            base.insertLayer(0, capa)
            capa_vis = pr.raiz.findLayer(capa.id())
            capa_vis.setItemVisibilityChecked(c in ("secciones_indicadores", "distritos", "limite_municipal"))
    tablas = pr.grupo("Tablas (metadatos y diccionario)")
    for c in ("metadatos_capas", "diccionario_campos"):
        t = QgsVectorLayer(f"{RES}|layername={c}", c, "ogr")
        pr.p.addMapLayer(t, False)
        tablas.addLayer(t)
    # 2) un grupo y un tema por figura, en el orden del informe
    temas = {}
    for fig in geo["figuras"]:
        pr.leyenda_capa = None
        temas[fig["nombre"]] = pr.capas_figura(fig)
        if pr.leyenda_capa is not None:
            pr.leyendas[fig["nombre"]] = pr.leyenda_capa
    # 3) diseños de impresión
    lays = disenos(pr, temas)
    lim = QgsVectorLayer(f"{RES}|layername=limite_municipal", "x", "ogr").extent()
    pr.p.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(lim.buffered(900), pr.p.crs()))
    if not pr.p.write(str(salida)):
        raise RuntimeError(f"No se pudo guardar {salida}")
    print(f"  {Path(salida).name}: {len(pr.p.mapLayers())} capas, {len(pr.p.mapThemeCollection().mapThemes())} temas, "
          f"{len(lays)} diseños de impresión")
    if carpeta_png:
        Path(carpeta_png).mkdir(parents=True, exist_ok=True)
        for l in lays:
            ex = QgsLayoutExporter(l)
            st = QgsLayoutExporter.ImageExportSettings()
            st.dpi = 220
            res = ex.exportToImage(str(Path(carpeta_png) / f"{l.name()}.png"), st)
            print(f"  exportado {l.name()}.png: {'OK' if res == QgsLayoutExporter.Success else res}")
    sys.stdout.flush()
    os._exit(0)   # exitQgis() falla en Windows con capas en memoria (ver qgis_estilos_geopackages.py)


if __name__ == "__main__":
    try:
        main(*sys.argv[1:4])
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
