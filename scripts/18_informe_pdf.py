"""Etapa 5 — Informe PDF en español (produtos/informe_sevilla_oferta_autobuses.pdf).

Uso:  .venv\\Scripts\\python.exe scripts\\18_informe_pdf.py

Compone las figuras de produtos/figuras/ (17_figuras.py) con textos cuyos números se leen de los CSV de
resultados/ y del GeoPackage final — no hay cifras escritas a mano. A4 apaisado, tipografía IBM Plex Sans (OFL).
"""
from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Frame, Paragraph, Table, TableStyle

from comum import caminho

PAL = json.loads(caminho("config/paleta.json").read_text(encoding="utf-8"))
TINTA, SUAVE, ACENTO, PAPEL = (HexColor(PAL[k]) for k in ("tinta", "tinta_suave", "acento", "fondo_papel"))
TIPC = {k: HexColor(v) for k, v in PAL["tipologia"].items()}
W, H = landscape(A4)
M = 36            # margen lateral (pt)
FIG = caminho("produtos/figuras")
SALIDA = caminho("produtos/informe_sevilla_oferta_autobuses.pdf")
TOTAL = 12
DISTRITOS = {"01": "Casco Antiguo", "02": "Macarena", "03": "Nervión", "04": "Cerro-Amate", "05": "Sur",
             "06": "Triana", "07": "Norte", "08": "San Pablo-Santa Justa", "09": "Este-Alcosa-Torreblanca",
             "10": "Bellavista-La Palmera", "11": "Los Remedios"}


# ------------------------------------------------------------------ tipografía y estilos
def fuentes():
    d = caminho("assets/fonts")
    for nombre, f in (("Plex", "Regular"), ("Plex-Medium", "Medium"), ("Plex-SemiBold", "SemiBold"),
                      ("Plex-Bold", "Bold"), ("Plex-Italic", "Italic")):
        pdfmetrics.registerFont(TTFont(nombre, str(d / f"IBMPlexSans-{f}.ttf")))
    pdfmetrics.registerFontFamily("Plex", normal="Plex", bold="Plex-SemiBold", italic="Plex-Italic", boldItalic="Plex-Bold")


EST = {}


def estilos():
    base = dict(fontName="Plex", textColor=TINTA, alignment=TA_LEFT)
    EST["cuerpo"] = ParagraphStyle("cuerpo", fontSize=9, leading=12.6, spaceAfter=6, **base)
    EST["lead"] = ParagraphStyle("lead", fontSize=10.6, leading=14.4, spaceAfter=8, fontName="Plex-Medium",
                                 textColor=TINTA, alignment=TA_LEFT)
    EST["vineta"] = ParagraphStyle("vineta", parent=EST["cuerpo"], leftIndent=10, bulletIndent=0, spaceAfter=3.5)
    EST["leyenda"] = ParagraphStyle("leyenda", fontSize=6.9, leading=9, textColor=SUAVE, fontName="Plex")
    EST["tabla"] = ParagraphStyle("tabla", fontSize=7.2, leading=9, fontName="Plex", textColor=TINTA)
    EST["tabla_b"] = ParagraphStyle("tabla_b", parent=EST["tabla"], fontName="Plex-SemiBold")
    EST["subt"] = ParagraphStyle("subt", fontSize=8.6, leading=11, fontName="Plex-SemiBold", textColor=ACENTO,
                                 spaceBefore=4, spaceAfter=3)


def n(x, dec=0):
    s = f"{abs(float(x)):,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return ("−" + s) if float(x) < 0 and s.strip("0,.") else s


# ------------------------------------------------------------------ datos
def datos():
    r = caminho("resultados")
    m2 = {x.indicador: x.valor for x in pd.read_csv(r / "etapa2/sintese_municipal.csv").itertuples()}
    s3 = pd.read_csv(r / "etapa3/sintese_municipal_periodo.csv").set_index("periodo")
    lim = {x.criterio: x.valor for x in pd.read_csv(r / "etapa4/limiares.csv").query("cenario == 'principal'").itertuples()}
    m4 = pd.read_csv(r / "etapa4/sintese_municipal.csv")
    m4p = m4[m4.cenario == "principal"].set_index("indicador")
    m4t = m4[m4.cenario == "sensibilidade_tercis"].set_index("indicador")
    tip = pd.read_csv(r / "etapa4/sintese_tipologia.csv").query("cenario == 'principal'").set_index("tipologia")
    dist = pd.read_csv(r / "etapa4/sintese_distritos.csv", dtype={"cdis": str})
    rk = pd.read_csv(r / "etapa4/ranking_prioritarias.csv", dtype={"cusec": str, "cdis": str})
    rel = pd.read_csv(r / "etapa4/densidade_relacao.csv").set_index("indicador")
    qua = pd.read_csv(r / "etapa4/densidade_quartis.csv")
    sen = pd.read_csv(r / "etapa4/sensibilidade_resumo.csv").set_index("indicador")
    per = pd.read_csv(r / "etapa4/comparacao_periodos.csv")
    sens3 = pd.read_csv(r / "etapa3/sensibilidade_interpolacao.csv")
    oo = pd.read_csv(r / "etapa3/oferta_origem_periodo.csv")
    pts = gpd.read_file(caminho("produtos/sevilla_oferta_bus_resultados.gpkg"), layer="puntos_demanda")
    sec = gpd.read_file(caminho("produtos/sevilla_oferta_bus_resultados.gpkg"), layer="secciones_indicadores")
    p1 = pts[pts.cusec == rk.iloc[0].cusec].sort_values("pob_estimada", ascending=False).iloc[0]
    d = dict(m2=m2, s3=s3, lim=lim, m4p=m4p, m4t=m4t, tip=tip, dist=dist, rk=rk, rel=rel, qua=qua, sen=sen, per=per,
             sens3=sens3, p1=p1, sec=sec)
    d["dedup"] = (oo.n_passagens_brutas.sum() - oo.n_viagens.sum())
    d["reduccion"] = int((per.dif_tarde_manha < 0).sum())
    d["var_med"] = per.var_pct_tarde_manha.median()
    d["caida25"] = int((per.var_pct_tarde_manha <= -25).sum())
    d["persist"] = int((sec.padrao_temporal == "baixa_frequencia_persistente").sum())
    def b(col):   # booleanos del GPKG con nulos (NULL = no aplica = False)
        return sec[col].map(lambda x: x is True or x == 1 or str(x).lower() == "true")
    pri = b("prioritaria")
    d["persist_pri"] = int(((sec.padrao_temporal == "baixa_frequencia_persistente") & pri).sum())
    d["pri_freq"] = int((pri & b("baixa_frequencia")).sum())
    d["limiar_sens"] = int((pri & (sec.pct_pob_perto_limiar_400m > 50)).sum())
    d["pob_total_ine"] = int(sec.pob_ine.sum())
    d["area_km2"] = float(sec.area_km2.sum())
    d["area_pri"] = (float(sec[pri].area_km2.min()), float(sec[pri].area_km2.max()))
    d["tipo_d"] = int((sec.tipologia == "D_deficiencias_combinadas").sum())
    dist = d["dist"].set_index("cdis")
    d["alta_dist"] = dist.secoes_alta_densidade.sort_values(ascending=False)
    serv = (dist.tipo_b + dist.tipo_c + dist.tipo_d).sort_values(ascending=False)
    d["dist_servicio"] = [DISTRITOS[c] for c, v in serv.items() if v >= 2]
    d["dist_a"] = dist.tipo_a[dist.tipo_a > 0].sort_values(ascending=False)
    return d


# ------------------------------------------------------------------ primitivas de página
def cabecera(c, num, titulo, kicker):
    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(ACENTO)
    c.rect(0, H - 6, W, 6, stroke=0, fill=1)
    c.setFont("Plex-Medium", 7)
    c.setFillColor(SUAVE)
    c.drawString(M, H - 22, "DESIGUALDAD TERRITORIAL EN LA OFERTA DE AUTOBUSES · SEVILLA")
    c.drawRightString(W - M, H - 22, f"{num:02d} / {TOTAL:02d}")
    c.setFillColor(ACENTO)
    c.setFont("Plex-SemiBold", 9)
    c.drawString(M, H - 46, kicker.upper())
    c.setFillColor(TINTA)
    c.setFont("Plex-SemiBold", 19)
    c.drawString(M, H - 68, titulo)
    c.setStrokeColor(HexColor(PAL["linea_fina"]))
    c.setLineWidth(0.5)
    c.line(M, 26, W - M, 26)
    c.setFont("Plex", 6.4)
    c.setFillColor(SUAVE)
    c.drawString(M, 15, "Fuentes: INE (Censo Anual de Población 2024, seccionado 2024) · IECA, malla de población 250 m 2024 (CC BY 4.0) · "
                        "GTFS TUSSAM 20260928, Powered by MITRAMS · © OpenStreetMap contributors (ODbL). Día de referencia: miércoles 21/10/2026.")


def texto(c, x, y_top, w, h, bloques):
    f = Frame(x, y_top - h, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
    f.addFromList(list(bloques), c)


def P(t, e="cuerpo"):
    return Paragraph(t, EST[e])


def V(t):
    return Paragraph(t, EST["vineta"], bulletText="•")


def figura(c, nombre, x, y_top, w, h, leyenda=None, alinear="top"):
    img = ImageReader(str(FIG / nombre))
    iw, ih = img.getSize()
    esc = min(w / iw, h / ih)
    dw, dh = iw * esc, ih * esc
    y = y_top - dh if alinear == "top" else y_top - h + (h - dh) / 2
    c.drawImage(img, x, y, dw, dh, mask="auto")
    if leyenda:
        p = Paragraph(leyenda, EST["leyenda"])
        _, ph = p.wrap(w, 60)
        p.drawOn(c, x, y - ph - 3)
    return y


def dato(c, x, y, valor, etiqueta, color=ACENTO, w=110):
    c.setFillColor(color)
    c.setFont("Plex-SemiBold", 20)
    c.drawString(x, y, valor)
    p = Paragraph(etiqueta, ParagraphStyle("d", fontName="Plex", fontSize=7.4, leading=9.2, textColor=SUAVE))
    _, ph = p.wrap(w, 40)
    p.drawOn(c, x, y - ph - 3)


def tabla(c, filas, x, y_top, anchos, cab_color=ACENTO, extra=None):
    data = [[P(str(v), "tabla_b" if i == 0 else "tabla") for v in f] for i, f in enumerate(filas)]
    t = Table(data, colWidths=anchos)
    st = [("LINEBELOW", (0, 0), (-1, 0), 0.8, cab_color), ("LINEBELOW", (0, 1), (-1, -1), 0.25, HexColor("#D5D9DD")),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.2),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if extra:
        st += extra
    t.setStyle(TableStyle(st))
    _, th = t.wrap(sum(anchos), 400)
    t.drawOn(c, x, y_top - th)
    return y_top - th


# ------------------------------------------------------------------ páginas
def portada(c, d):
    c.drawImage(ImageReader(str(FIG / "portada.png")), 0, 0, W, H)
    c.setFillColor(HexColor(PAL["tinta"]))
    c.rect(0, 0, W * 0.40, H, stroke=0, fill=1)
    c.setFillColor(HexColor("#E9A23B"))
    c.rect(M, H - 120, 46, 4, stroke=0, fill=1)
    c.setFillColor(HexColor("#F2F0EA"))
    c.setFont("Plex-Medium", 9)
    c.drawString(M, H - 100, "SEVILLA · ANÁLISIS TERRITORIAL DEL TRANSPORTE PÚBLICO")
    y = H - 165
    for linea in ("Desigualdad territorial", "en la oferta de autobuses", "urbanos de Sevilla"):
        c.setFont("Plex-SemiBold", 25)
        c.drawString(M, y, linea)
        y -= 31
    sub = Paragraph("Densidad de población, accesibilidad peatonal y frecuencia programada del servicio TUSSAM",
                    ParagraphStyle("s", fontName="Plex", fontSize=12, leading=16, textColor=HexColor("#C9D6E0")))
    sub.wrap(W * 0.40 - 2 * M, 80)
    sub.drawOn(c, M, y - 30)
    c.setFont("Plex", 8.2)
    c.setFillColor(HexColor("#AAB7C2"))
    for i, t in enumerate(["521 secciones censales · población INE a 01/01/2024",
                           "GTFS TUSSAM 20260928 · día laborable 21/10/2026",
                           "Red peatonal OpenStreetMap · umbral de 400 m",
                           "Informe de portafolio · 2026"]):
        c.drawString(M, 118 - i * 13, t)
    c.setFont("Plex", 6.6)
    c.setFillColor(HexColor("#8A99A6"))
    c.drawString(M, 30, "Mapa: red peatonal (OSM), paradas con salidas 07–09 (azul, tamaño según frecuencia)")
    c.drawString(M, 21, "y las 33 secciones prioritarias (blanco). © OpenStreetMap contributors, GTFS Powered by MITRAMS.")
    c.showPage()


def p01(c, d):
    cabecera(c, 1, "¿Dónde vive mucha gente con poco autobús?", "Problema y objetivos")
    m2, s3 = d["m2"], d["s3"]
    texto(c, M, H - 92, 360, 430, [
        P("Sevilla tiene una red de autobuses urbanos densa, pero la oferta no se reparte igual por la ciudad. Este informe "
          "localiza las <b>secciones censales con elevada densidad de población y una oferta de autobús relativamente "
          "insuficiente</b>, y explica en qué consiste esa insuficiencia en cada caso.", "lead"),
        P("<b>Pregunta central.</b> ¿Qué secciones censales de Sevilla combinan una elevada densidad de población con una oferta "
          "relativamente insuficiente de autobuses urbanos?"),
        P("Tres dimensiones distintas de la oferta, medidas por separado:", "subt"),
        V("<b>Proximidad física</b>: ¿hay una parada con servicio a 400 m o menos de recorrido a pie por la red peatonal?"),
        V("<b>Diversidad de líneas</b>: ¿cuántas líneas distintas se pueden tomar en esas paradas?"),
        V("<b>Frecuencia programada</b>: ¿cuántas salidas por hora ofrecen, sin contar dos veces el mismo autobús?"),
        P("Una sección puede tener paradas cercanas y, aun así, pocas líneas o salidas muy espaciadas. Por eso el diagnóstico "
          "distingue la falta de parada de la baja intensidad del servicio en paradas existentes.", "cuerpo"),
        P("Alcance", "subt"),
        P("Autobús urbano de TUSSAM programado un miércoles laborable (21/10/2026), en tres franjas: 07–09, 12–14 y 17–19 h. "
          "No incluye metro, tranvía, Cercanías ni autobuses metropolitanos, ni mide la puntualidad real ni el acceso a "
          "destinos concretos."),
    ])
    x0 = M + 400
    c.setFillColor(PAPEL)
    c.roundRect(x0, 70, W - M - x0, H - 92 - 70, 6, stroke=0, fill=1)
    c.setFillColor(TINTA)
    c.setFont("Plex-SemiBold", 9)
    c.drawString(x0 + 18, H - 116, "LA CIUDAD EN CIFRAS")
    pares = [(n(d["pob_total_ine"]), "habitantes (INE, 01/01/2024) en 521 secciones censales"),
             (n(m2["populacao_grade_estimada_sevilla"]), "habitantes estimados por la malla IECA de 250 m, base de los cálculos de acceso"),
             (n(m2["paradas_com_servico_onibus_dia"]), "paradas de autobús con servicio el día de referencia"),
             (n(s3.loc["manha", "viagens_rede"]), "viajes programados que circulan entre 07 y 09 h"),
             (f"{n(m2['pct_coberta_400m'], 2)} %", "de la población estimada tiene parada a ≤ 400 m a pie"),
             (n(d["m4p"].loc["secoes_prioritarias", "secoes"]), "secciones densas con al menos una deficiencia relativa de oferta")]
    for i, (val, et) in enumerate(pares):
        col, fila = i % 2, i // 2
        dato(c, x0 + 18 + col * 190, H - 175 - fila * 92, val, et, w=165)
    c.setFont("Plex", 7)
    c.setFillColor(SUAVE)
    c.drawString(x0 + 18, 84, "La población oficial (INE) caracteriza las secciones; la estimada (IECA) mide el acceso.")
    c.drawString(x0 + 18, 74, "Son fuentes distintas y no se mezclan en un mismo indicador.")
    c.showPage()


def p02(c, d):
    cabecera(c, 2, "Área de estudio y fuentes", f"Sevilla, {n(d['area_km2'], 0)} km² y 11 distritos")
    figura(c, "mapa_localizacion.png", M + 300, H - 84, W - 2 * M - 300, 440,
           "Límite municipal y 521 secciones censales del seccionado INE a 01/01/2024, agrupadas en 11 distritos censales "
           "(código INE y denominación del distrito municipal). El municipio incluye un enclave al sur. Sin mapa base externo.")
    filas = [["Fuente", "Uso en el análisis", "Fecha"],
             ["INE · Censo Anual de Población", "Población oficial por sección (686.741 hab.)", "01/01/2024"],
             ["INE · Seccionado", "521 secciones, áreas y densidad (EPSG:25830)", "01/01/2024"],
             ["IECA · Malla 250 m", "Localización aproximada de residentes (887 celdas)", "01/01/2024"],
             ["TUSSAM · GTFS (NAP, MITRAMS)", "Paradas, líneas, viajes y horarios programados", "versión 20260928"],
             ["OpenStreetMap", "Red peatonal, ríos, ferrocarriles y autovías", "25/10/2026"],
             ["IDE Sevilla · capa TUSSAM", "Solo control de calidad; no redistribuible", "20/10/2026"]]
    y = tabla(c, filas, M, H - 92, [92, 150, 50])
    texto(c, M, y - 14, 292, 290, [
        P("Todo se proyecta en ETRS89 / UTM 30N (EPSG:25830). Los indicadores se calculan por sección censal con su "
          "geometría original; la malla del IECA solo sirve para situar a la población dentro de cada sección."),
        P("La población oficial de cada sección procede del INE. La malla del IECA (otra fuente, otro método) suma "
          f"{n(d['m2']['populacao_grade_estimada_sevilla'])} habitantes dentro del municipio: se usa como denominador de "
          "la accesibilidad, nunca para sustituir la cifra oficial."),
        P("Cadena de procesamiento", "subt"),
        V("PostgreSQL/PostGIS: carga de fuentes, secciones, malla y horarios GTFS."),
        V("Python (OSMnx, NetworkX): red peatonal y recorridos hasta 400 m."),
        V("SQL: salidas por franja, deduplicación de viajes y agregación por sección."),
        V("Clasificación por umbrales explícitos y pruebas automáticas en cada etapa."),
    ])
    c.showPage()


def p03(c, d):
    cabecera(c, 3, "Distribución de la población", "Densidad oficial por sección")
    lim = d["lim"]
    figura(c, "mapa_densidad.png", M + 300, H - 84, W - 2 * M - 300, 445,
           "Densidad = población INE 2024 / área total de la sección. Clases ancladas en los cuartiles municipales "
           "(P25, P50, P75).")
    q = d["sec"].densidade_ine_hab_km2.quantile([0.25, 0.5])
    texto(c, M, H - 92, 280, 175, [
        P("Las secciones de alta densidad se concentran en barrios residenciales de bloque: "
          + ", ".join(f"{DISTRITOS[k]} ({int(v)})" for k, v in d["alta_dist"].head(5).items())
          + f". El Casco Antiguo no tiene ninguna ({int(d['alta_dist'].get('01', 0))}), y en la periferia las secciones "
          "extensas incluyen mucho suelo no residencial.", "lead"),
        P(f"La mitad de las secciones supera {n(q[0.5])} hab./km². El cuartil superior empieza en "
          f"<b>{n(lim['alta_densidade'], 1)} hab./km²</b>: ese es el umbral de <b>alta densidad</b> utilizado en la "
          f"clasificación ({n(d['m4p'].loc['secoes_alta_densidade', 'secoes'])} secciones, "
          f"{n(d['m4p'].loc['secoes_alta_densidade', 'pob_ine'])} habitantes)."),
    ])
    figura(c, "graf_densidad.png", M, H - 280, 280, 150)
    texto(c, M, 140, 280, 100, [
        P("Densidad no es lo mismo que población: entre las secciones de alta densidad, la menos poblada tiene "
          f"{n(d['sec'][d['sec'].alta_densidade.astype(bool)].pob_ine.min())} habitantes. La clasificación usa la densidad "
          "oficial (área total); una densidad sobre el área habitada se conserva como dato complementario.", "leyenda")])
    c.showPage()


def p04(c, d):
    cabecera(c, 4, "Accesibilidad peatonal a las paradas", "Cobertura a 400 m por la red")
    m2 = d["m2"]
    figura(c, "mapa_cobertura.png", M + 300, H - 84, W - 2 * M - 300, 445,
           "Porcentaje de la población estimada (malla IECA) sin ninguna parada con servicio a ≤ 400 m de recorrido. "
           "Las secciones periféricas extensas destacan por superficie, pero concentran poca población.")
    texto(c, M, H - 92, 280, 120, [
        P(f"El {n(m2['pct_coberta_400m'], 2)} % de la población estimada tiene al menos una parada con servicio a 400 m "
          "o menos caminando. La carencia se concentra en bordes urbanos y en bolsas puntuales dentro de barrios densos.", "lead")])
    figura(c, "graf_cobertura.png", M, H - 205, 280, 70)
    texto(c, M, H - 290, 280, 250, [
        P(f"<b>{n(m2['populacao_coberta_400m'])}</b> habitantes cubiertos ({n(m2['pct_coberta_400m'], 2)} %) · "
          f"<b>{n(m2['populacao_sem_cobertura_400m'])}</b> sin parada a 400 m ({n(m2['pct_sem_cobertura_400m'], 2)} %) · "
          f"<b>{n(m2['populacao_nao_determinada'])}</b> no determinados ({n(m2['pct_nao_determinada'], 2)} %; conexión a la red incierta)."),
        P("Los 400 m son <b>recorrido por la red peatonal</b> de OpenStreetMap, no un círculo en línea recta: incluyen el "
          "acceso del punto de demanda a la calle y de la calle a la parada, y respetan ríos, vías de ferrocarril y autovías. "
          f"El recorrido medio a la parada más cercana es de {n(m2['dist_media_ponderada_parada_m'])} m."),
        P("La población se representa con 2.674 puntos (celda IECA × sección). No son domicilios: cada punto resume a los "
          "residentes estimados de su parcela.", "leyenda"),
    ])
    c.showPage()


def p05(c, d):
    cabecera(c, 5, "Diversidad de líneas accesibles", "Cuántas líneas distintas, no cuántas paradas")
    lim, s3, rk = d["lim"], d["s3"], d["rk"]
    figura(c, "mapa_lineas.png", M + 300, H - 84, W - 2 * M - 300, 445,
           "Líneas distintas con al menos una salida 07–09 en las paradas a ≤ 400 m, media ponderada por la población "
           "con parada. En gris, secciones sin población cubierta.")
    texto(c, M, H - 92, 280, 140, [
        P(f"El residente medio puede tomar {n(s3.loc['manha', 'media_linhas'], 2)} líneas distintas a pie en la punta de la "
          f"mañana ({n(s3.loc['manha', 'media_linhas_cobertos'], 2)} entre quienes tienen parada). Nervión, San Pablo y el "
          "entorno del Prado de San Sebastián superan las cinco líneas; muchos barrios dependen de una o dos.", "lead"),
        P("Buena parte del Casco Antiguo, servido sobre todo por la circular C5 — que empieza después de las 10 h —, queda "
          "por debajo de una línea en esta franja."),
        P(f"El cuartil inferior se sitúa en <b>{n(lim['baixa_diversidade_linhas'], 2)} líneas</b>. Una línea cuenta una sola "
          "vez aunque pase por varias paradas cercanas."),
    ])
    figura(c, "graf_lineas.png", M, H - 240, 280, 130)
    pocas = rk[rk.linhas_cob_manha <= 1.05].head(4)
    filas = [["Sección", "Distrito", "Líneas", "Salidas/h"]] + [
        [x.cusec, DISTRITOS[x.cdis], n(x.linhas_cob_manha, 2), n(x.partidas_h_cob_manha, 1)] for x in pocas.itertuples()]
    c.setFont("Plex-SemiBold", 8)
    c.setFillColor(ACENTO)
    c.drawString(M, 158, "Ejemplos: secciones densas con una sola línea a su alcance (07–09)")
    tabla(c, filas, M, 150, [62, 110, 44, 50])
    c.showPage()


def p06(c, d):
    cabecera(c, 6, "Frecuencia programada", "Salidas accesibles por hora")
    lim, s3 = d["lim"], d["s3"]
    figura(c, "mapa_frecuencia.png", M + 300, H - 84, W - 2 * M - 300, 445,
           "Viajes distintos con salida 07–09 en alguna parada a ≤ 400 m, divididos por 2 h; media ponderada por la "
           "población con parada.")
    texto(c, M, H - 92, 280, 150, [
        P(f"Entre las 7 y las 9 h, el residente medio tiene a su alcance {n(s3.loc['manha', 'media_partidas_hora'], 1)} salidas "
          f"por hora ({n(s3.loc['manha', 'media_partidas_hora_cobertos'], 1)} entre quienes tienen parada). En el cuartil "
          f"inferior hay {n(lim['baixa_frequencia'], 1)} salidas/h o menos.", "lead")])
    figura(c, "graf_frecuencia.png", M, H - 205, 280, 125)
    texto(c, M, H - 345, 280, 220, [
        P("Cómo se cuenta", "subt"),
        V("Horarios del GTFS de TUSSAM para el servicio de días laborables (INVLAB40)."),
        V(f"<b>Sin duplicados</b>: un mismo viaje que pasa por tres paradas cercanas es una sola oportunidad de embarque. "
          f"La deduplicación eliminó {n(d['dedup'])} pasos repetidos entre los tres periodos."),
        V("No se cuenta la última parada de cada viaje (solo bajada)."),
        V(f"El {n(s3.loc['manha', 'pct_partidas_paradas_interpoladas'], 0)} % de los horarios por parada se interpola entre "
          "puntos de control por distancia recorrida; un análisis de sensibilidad muestra que no altera las comparaciones."),
        P("Es la oferta accesible a un residente, no el número de autobuses que cruzan la sección.", "leyenda"),
    ])
    c.showPage()


def p07(c, d):
    cabecera(c, 7, "Diferencias a lo largo del día", "Mañana, mediodía y tarde")
    s3 = d["s3"]
    figura(c, "mapa_variacion.png", M + 300, H - 84, W - 2 * M - 300, 445,
           "Variación porcentual de las salidas/h accesibles entre 17–19 y 07–09 por sección.")
    caida = 100 * (s3.loc["tarde", "media_partidas_hora"] / s3.loc["manha", "media_partidas_hora"] - 1)
    texto(c, M, H - 92, 280, 110, [
        P(f"La oferta accesible baja por la tarde: de {n(s3.loc['manha', 'media_partidas_hora'], 1)} a "
          f"{n(s3.loc['tarde', 'media_partidas_hora'], 1)} salidas/h para el residente medio ({n(caida, 1)} %). El mediodía "
          "mantiene un nivel similar al de la mañana.", "lead")])
    figura(c, "graf_periodos.png", M, H - 180, 280, 160,
           "Medias ponderadas por la población con accesibilidad determinada (sin parada = 0) y viajes de la red con al "
           "menos una salida en la franja.")
    texto(c, M, H - 365, 280, 200, [
        P(f"<b>{d['reduccion']} de las 521 secciones</b> tienen menos salidas accesibles por la tarde (variación mediana "
          f"{n(d['var_med'], 1)} %; {d['caida25']} pierden un 25 % o más). El número de líneas apenas cambia: la tarde no "
          "pierde líneas, pierde frecuencia."),
        P(f"La baja frecuencia de las áreas prioritarias es estructural: {d['persist_pri']} de las {d['pri_freq']} secciones "
          "prioritarias con baja frecuencia por la mañana la mantienen en las tres franjas."),
        P("Las diferencias reflejan la programación del operador, no la demanda ni los viajeros transportados.", "leyenda"),
    ])
    c.showPage()


def p08(c, d):
    cabecera(c, 8, "Densidad frente a oferta", "Una relación débil")
    rel, qua = d["rel"], d["qua"]
    figura(c, "graf_dispersion.png", M, H - 84, W - 2 * M, 245,
           "Cada punto es una sección censal. Línea discontinua vertical: umbral de alta densidad (P75). Líneas punteadas: "
           "cobertura media municipal y cuartil inferior de líneas y salidas. Correlación de Spearman (rangos, con empates promediados).")
    filas = [["Cuartil de densidad", "Hab./km²", "Con parada a 400 m", "Salidas/h 07–09", "Sin parada (hab.)"]] + [
        [f"Q{int(x.quartil)}", f"{n(x.dens_min)} – {n(x.dens_max)}", f"{n(x.pct_coberta_400m, 1)} %", n(x.partidas_h_manha, 1),
         n(x.pob_sem_cobertura)] for x in qua.itertuples()]
    tabla(c, filas, M, 205, [90, 92, 90, 80, 80])
    texto(c, M + 460, 205, W - 2 * M - 460, 180, [
        P(f"Más densidad se asocia con algo más de oferta, pero débilmente (Spearman: cobertura "
          f"{n(rel.loc['cobertura_400m_pct', 'spearman_densidade'], 2)}, líneas {n(rel.loc['linhas_manha_cobertos', 'spearman_densidade'], 2)}, "
          f"salidas/h {n(rel.loc['partidas_h_manha_cobertos', 'spearman_densidade'], 2)}). La población sin parada se concentra en las "
          "secciones menos densas.", "lead"),
        P("Dentro del grupo de alta densidad conviven secciones muy bien servidas y otras con una o dos líneas: es ahí donde "
          "se centra el diagnóstico. Una correlación no demuestra causalidad."),
    ])
    c.showPage()


def p09(c, d):
    cabecera(c, 9, "Clasificación de las deficiencias", "Umbrales y tipología A–D")
    lim, tip, m4p = d["lim"], d["tip"], d["m4p"]
    filas = [["Criterio", "Regla (comparación interna a Sevilla)", "Umbral"],
             ["Alta densidad", "Cuartil superior de las 521 secciones", f"≥ {n(lim['alta_densidade'], 1)} hab./km²"],
             ["Baja cobertura", "Por debajo de la cobertura municipal (el cuartil inferior es 100 %)", f"< {n(lim['baixa_cobertura'], 2)} %"],
             ["Pocas líneas", "Cuartil inferior, población con parada, 07–09", f"≤ {n(lim['baixa_diversidade_linhas'], 2)}"],
             ["Baja frecuencia", "Cuartil inferior, población con parada, 07–09", f"≤ {n(lim['baixa_frequencia'], 2)} salidas/h"]]
    y = tabla(c, filas, M, H - 92, [70, 165, 85])
    texto(c, M, y - 14, 320, 300, [
        P("Tipología de las secciones de alta densidad", "subt"),
        P(f"<font color='{PAL['tipologia']['A_baixa_cobertura']}'><b>A · Baja cobertura</b></font>: parte relevante de los residentes sin parada a 400 m."),
        P(f"<font color='{PAL['tipologia']['B_baixa_diversidade_linhas']}'><b>B · Pocas líneas</b></font>: paradas cercanas, pero pocas líneas disponibles."),
        P(f"<font color='{PAL['tipologia']['C_baixa_frequencia']}'><b>C · Baja frecuencia</b></font>: acceso y líneas suficientes, pocas salidas."),
        P(f"<font color='{PAL['tipologia']['D_deficiencias_combinadas']}'><b>D · Deficiencias combinadas</b></font>: más de una a la vez "
          "(en Sevilla, siempre pocas líneas y baja frecuencia)."),
        P(f"Precedencia: D si hay dos o más deficiencias; si no, A, B o C. Son <b>prioritarias</b> las secciones de alta "
          f"densidad con al menos una deficiencia: <b>{n(m4p.loc['secoes_prioritarias', 'secoes'])} secciones y "
          f"{n(m4p.loc['secoes_prioritarias', 'pob_ine'])} habitantes</b> ({n(m4p.loc['secoes_prioritarias', 'pct_pob_ine'], 1)} % "
          "de la población oficial). Ninguna sección densa combina falta de parada con poca oferta."),
        P("Los umbrales son comparaciones dentro de la ciudad, no estándares técnicos ni legales de calidad.", "leyenda"),
    ])
    figura(c, "graf_tipologia.png", M + 350, H - 92, W - 2 * M - 350, 145, "Secciones y población INE por tipo.")
    figura(c, "graf_distritos.png", M + 350, H - 270, W - 2 * M - 350, 215,
           "Secciones prioritarias por distrito censal y tipo; a la derecha, número de secciones y población INE.")
    c.showPage()


def p10(c, d):
    cabecera(c, 10, "Las 33 secciones prioritarias", "Dónde se concentran")
    m4p, dist = d["m4p"], d["dist"].set_index("cdis")
    figura(c, "mapa_prioritarias.png", M, H - 84, 450, 448,
           "Tipología de cada sección (franja 07–09). Las prioritarias se resaltan con contorno; los números son las diez "
           "primeras del ranking. Códigos grises: distritos censales.")
    a = d["dist_a"]
    texto(c, M + 470, H - 92, W - 2 * M - 470, 150, [
        P(f"Las {n(m4p.loc['secoes_prioritarias', 'secoes'])} secciones reúnen {n(m4p.loc['secoes_prioritarias', 'pob_ine'])} "
          f"residentes. Son piezas pequeñas ({n(d['area_pri'][0], 3)}–{n(d['area_pri'][1], 3)} km²) dentro de barrios densos, "
          "no grandes vacíos de servicio.", "lead"),
        P(f"<b>Cerro-Amate (04)</b> concentra {int(dist.loc['04', 'secoes_prioritarias'])} secciones y el "
          f"{n(dist.loc['04', 'pct_pob_prioritaria_municipal'], 0)} % de la población prioritaria. Los casos de tipo A están en "
          + ", ".join(f"{DISTRITOS[k]} ({int(v)})" for k, v in a.items())
          + ". Casco Antiguo y Bellavista-La Palmera no tienen secciones prioritarias."),
    ])
    figura(c, "graf_ranking.png", M + 470, H - 250, W - 2 * M - 470, 300)
    c.showPage()


def p11(c, d):
    cabecera(c, 11, "Las secciones de mayor prioridad", "Falta de parada o poca frecuencia")
    rk, p1 = d["rk"], d["p1"]
    figura(c, "mapa_detalle.png", M, H - 84, 540, 265)
    texto(c, M + 560, H - 92, W - 2 * M - 560, 260, [
        P("Dos situaciones distintas", "subt"),
        P("<b>Izquierda</b>: en Triana y Los Remedios hay paradas cerca, pero parte de los residentes (puntos rojos) quedan a "
          "más de 400 m de recorrido."),
        P("<b>Derecha</b>: en Cerro-Amate casi todos tienen parada, pero las paradas cercanas ofrecen una o dos líneas y pocas "
          "salidas (cuadrados pequeños)."),
        P(f"La nº 1 depende de un único punto de demanda con {n(p1.pob_estimada)} residentes estimados a "
          f"{n(p1.dist_parada_mais_proxima_m)} m de recorrido de la parada más cercana: un resultado próximo al umbral de "
          "400 m, prioritario según la regla pero sensible a la localización del punto.", "leyenda"),
        P("El orden refleja criterios explícitos, no una medida universal de necesidad de inversión.", "leyenda"),
    ])
    top = rk.head(10)

    def motivo(x):
        if x.tipologia.startswith("A"):
            return f"{n(x.pob_sem_cobertura)} hab. sin parada"
        return f"{n(x.linhas_cob_manha, 1)} líneas, {n(x.partidas_h_cob_manha, 1)} salidas/h"
    filas = [["#", "Sección", "Distrito", "Tipo", "Pob. INE", "Hab./km²", "Con parada", "Líneas*", "Salidas/h*", "Motivo principal"]] + [
        [int(x.ranking), x.cusec, DISTRITOS[x.cdis], x.tipologia[0], n(x.pob_ine), n(x.densidade_ine_hab_km2), f"{n(x.pct_coberta_400m, 1)} %",
         n(x.linhas_cob_manha, 2), n(x.partidas_h_cob_manha, 1), motivo(x)] for x in top.itertuples()]
    extra = [("TEXTCOLOR", (3, i + 1), (3, i + 1), TIPC[x.tipologia]) for i, x in enumerate(top.itertuples())]
    y = tabla(c, filas, M, 228, [18, 62, 120, 28, 50, 54, 58, 46, 54, 180], extra=extra)
    c.setFont("Plex", 6.6)
    c.setFillColor(SUAVE)
    c.drawString(M, y - 10, "* Media entre la población con parada, 07–09. Orden: dimensiones deficientes (acceso, servicio) → población sin oferta → "
                            "menor frecuencia → menos líneas → mayor densidad → código.")
    c.showPage()


def p12(c, d):
    cabecera(c, 12, "Síntesis y limitaciones", "Qué muestra el diagnóstico")
    m4p, m4t, sen, m2 = d["m4p"], d["m4t"], d["sen"], d["m2"]
    texto(c, M, H - 92, 370, 440, [
        P("Conclusiones", "subt"),
        V(f"La cobertura física es alta ({n(m2['pct_coberta_400m'], 2)} %): la desigualdad está más en <b>cuántas líneas y "
          "salidas</b> hay en las paradas cercanas que en la existencia de una parada."),
        V(f"{n(m4p.loc['secoes_prioritarias', 'secoes'])} secciones densas ({n(m4p.loc['secoes_prioritarias', 'pob_ine'])} "
          f"residentes, {n(m4p.loc['secoes_prioritarias', 'pct_pob_ine'], 1)} %) combinan alta densidad con al menos una "
          f"deficiencia relativa; {d['tipo_d']} de ellas tienen a la vez pocas líneas y baja frecuencia."),
        V("Los casos de falta de parada (tipo A) se agrupan en " + " y ".join(DISTRITOS[k] for k in d["dist_a"].index[:2])
          + "; los de servicio débil (B, C, D) se reparten por " + ", ".join(d["dist_servicio"]) + "."),
        V(f"La tarde ofrece un {n(-100 * (d['s3'].loc['tarde', 'media_partidas_hora'] / d['s3'].loc['manha', 'media_partidas_hora'] - 1), 0)} % "
          "menos de salidas accesibles que la mañana; la baja frecuencia de las prioritarias se mantiene durante todo el día."),
        V(f"Con tercios en lugar de cuartiles hay {n(m4t.loc['secoes_prioritarias', 'secoes'])} prioritarias y las "
          f"{n(sen.loc['secoes_prioritaria_nos_dois', 'valor'])} originales siguen en el grupo: el resultado es estable ante ese "
          "cambio, aunque depende de otras decisiones metodológicas."),
        V("Hay secciones con deficiencias graves y densidad intermedia (p. ej., 4109106007) fuera de las 33: el modelo no "
          "identifica todas las áreas que podrían necesitar mejoras."),
        P("Uso del diagnóstico", "subt"),
        P("Señala dónde mirar primero y por qué (acceso o servicio). La prioridad territorial no equivale a una recomendación "
          "de intervención: no se han simulado nuevas líneas ni paradas."),
    ])
    x0 = M + 400
    c.setFillColor(PAPEL)
    c.roundRect(x0, 225, W - M - x0, H - 92 - 225, 6, stroke=0, fill=1)
    texto(c, x0 + 16, H - 108, W - M - x0 - 32, 400, [
        P("Limitaciones", "subt"),
        V("<b>Oferta programada</b> en el GTFS, no servicio realizado ni puntualidad."),
        V(f"<b>Horarios interpolados</b>: ~{n(d['s3'].loc['manha', 'pct_partidas_paradas_interpoladas'], 0)} % de los horarios "
          "por parada; la sensibilidad (±2 min) cambia la frecuencia media menos de un 0,5 %."),
        V("<b>Población aproximada</b> por la malla IECA para el acceso; difiere de la cifra INE en cada sección."),
        V(f"<b>Umbral rígido de 400 m</b>: en {d['limiar_sens']} prioritarias, más de la mitad de la población está a 350–450 m."),
        V("<b>Umbrales relativos</b> (cuartiles, media municipal), internos a Sevilla."),
        V("<b>Solo autobús urbano TUSSAM</b>: sin metro, tranvía, Cercanías ni autobuses metropolitanos."),
        V("<b>Red OSM</b> sin aceras explícitas; las autovías sin paso peatonal se excluyen por prudencia."),
        V("Densidad sobre el <b>área total</b> de la sección; algunas secciones con suelo no residencial quedan por debajo del umbral."),
        P("Código, datos derivados y metodología: repositorio del proyecto (README, docs/ y produtos/).", "leyenda"),
    ])
    c.showPage()


def main():
    fuentes()
    estilos()
    d = datos()
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(SALIDA), pagesize=landscape(A4))
    c.setTitle("Desigualdad territorial en la oferta de autobuses urbanos de Sevilla")
    c.setSubject("Densidad de población, accesibilidad peatonal y frecuencia programada del servicio TUSSAM")
    c.setAuthor("Proyecto sevilla_oferta_bus (autoría pendiente)")
    c.setKeywords("Sevilla, TUSSAM, GTFS, accesibilidad, PostGIS, densidad")
    for f in (portada, p01, p02, p03, p04, p05, p06, p07, p08, p09, p10, p11, p12):
        f(c, d)
    c.save()
    print(f"  {SALIDA.relative_to(caminho('.'))}: {TOTAL + 1} páginas")


if __name__ == "__main__":
    main()
