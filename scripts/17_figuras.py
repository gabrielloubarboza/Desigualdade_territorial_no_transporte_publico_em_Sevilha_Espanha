"""Etapa 5 — Mapas y gráficos del informe (produtos/figuras/), a partir de los GeoPackages finales.

Uso:  .venv\\Scripts\\python.exe scripts\\17_figuras.py

No consulta el banco: lee produtos/sevilla_oferta_bus_resultados.gpkg y _contexto_osm.gpkg. Mapas por
sección censal con sus geometrías originales; sin mapas base de servicios externos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

import visual as v
from visual import PALETA, SUAVE, TINTA, TIP_ORDEN, num, plt

MM = 1 / 25.4


def col(s, cortes, colores, nulo="#E3E3E0"):
    return [c or nulo for c in v.clasificar(s, cortes, colores)]


def secc_plot(ax, sec, colores, lw=0.12, ec="white", z=2):
    sec.assign(_c=colores).plot(ax=ax, color=sec.assign(_c=colores)._c, ec=ec, lw=lw, zorder=z)


def mapa_simple(base, colores, items, titulo, nombre, nota=None, size=(172, 150)):
    fig, ax = plt.subplots(figsize=(size[0] * MM, size[1] * MM))
    v.mapa_base(ax, base, etiquetas_distrito=True)
    secc_plot(ax, base.secciones, colores)
    v.leyenda(ax, items, titulo, loc="lower right")
    v.escala_norte(ax)
    if nota:
        ax.text(0.01, 0.995, nota, transform=ax.transAxes, fontsize=6.2, color=SUAVE, va="top")
    return v.guardar(fig, nombre)


# ------------------------------------------------------------------ portada
def portada(base):
    red = v.cargar("red_peatonal", v.CONTEXTO)
    red = red[red.utilizable == 1]
    par = v.cargar("paradas_autobus")
    pri = base.secciones[base.secciones.prioritaria == 1]
    fig = plt.figure(figsize=(297 * MM, 210 * MM), facecolor=TINTA)
    ax = fig.add_axes([0.36, 0.0, 0.64, 1.0])
    ax.set_facecolor(TINTA)
    x0, y0, x1, y1 = base.limite.total_bounds
    ax.set_xlim(x0 + 600, x1 - 5200)     # recorte: núcleo urbano (sin la cola oriental ni el enclave sur)
    ax.set_ylim(y0 + 3600, y1 - 900)
    ax.set_aspect("equal")
    ax.set_axis_off()
    base.agua.plot(ax=ax, color="#24394A", lw=0, zorder=1)
    red.plot(ax=ax, color="#3E5466", lw=0.18, zorder=2)
    pri.plot(ax=ax, color="#F2F0EA", lw=0, zorder=3)   # portada: sin simbología A–D (color neutro único)
    s = par[par.salidas_h_manana > 0]
    ax.scatter(s.geometry.x, s.geometry.y, s=1.2 + s.salidas_h_manana / 6, c="#8FBDD8", lw=0, alpha=0.85, zorder=4)
    base.limite.boundary.plot(ax=ax, color="#8A99A6", lw=0.6, zorder=5)
    return v.guardar(fig, "portada.png", recortar=False)


# ------------------------------------------------------------------ localización
def localizacion(base):
    ccaa = v.cargar("contexto_ccaa")
    fig, ax = plt.subplots(figsize=(172 * MM, 150 * MM))
    v.mapa_base(ax, base, etiquetas_distrito=False)
    base.secciones.plot(ax=ax, color="#F4F2EE", ec="#B9BEC4", lw=0.15, zorder=2)
    for _, d in base.distritos.iterrows():
        p = d.geometry.representative_point()
        ax.text(p.x, p.y, f"{d.cdis}\n{d.nombre}", fontsize=6.2, color=TINTA, ha="center", va="center", zorder=9,
                linespacing=1.0, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.8))
    ax.text(0.108, 0.40, "Río Guadalquivir", transform=ax.transAxes, rotation=84, fontsize=6.5, color="#4F7A93", style="italic")
    v.escala_norte(ax)
    ins = fig.add_axes([0.70, 0.06, 0.28, 0.24])
    ccaa.plot(ax=ins, color="#E7E5DF", ec="white", lw=0.3)
    ccaa[ccaa.cca == "01"].plot(ax=ins, color="#BDA3D0", ec="white", lw=0.3)
    c = base.limite.geometry.iloc[0].centroid
    ins.plot(c.x, c.y, "o", ms=3.5, color=TINTA)
    ins.set_xlim(-60000, 1150000)
    ins.set_ylim(3950000, 4880000)
    ins.set_aspect("equal")
    ins.set_xticks([])
    ins.set_yticks([])
    ins.set_xlabel("")
    ins.set_ylabel("")
    for sp in ins.spines.values():
        sp.set_visible(True)
        sp.set_color("#B9BEC4")
    ins.text(0.03, 0.04, "Andalucía", transform=ins.transAxes, fontsize=5.8, color="#6B4C93")
    return v.guardar(fig, "mapa_localizacion.png")


# ------------------------------------------------------------------ densidad
def densidad(base, lim):
    s = base.secciones
    p25, p50 = np.percentile(s.densidade_ine_hab_km2, [25, 50])
    cortes = [0, 5000, p25, p50, lim["alta_densidade"], 45000, 1e9]
    etq = ["< 5.000", f"5.000 – {num(p25)}", f"{num(p25)} – {num(p50)}", f"{num(p50)} – {num(lim['alta_densidade'])}",
           f"{num(lim['alta_densidade'])} (P75) – 45.000", "≥ 45.000"]
    c = col(s.densidade_ine_hab_km2, cortes, PALETA["densidad"])
    mapa_simple(base, c, list(zip(PALETA["densidad"], etq)), "Habitantes/km² (INE 2024)", "mapa_densidad.png")
    fig, ax = plt.subplots(figsize=(80 * MM, 52 * MM))
    d = s.densidade_ine_hab_km2 / 1000
    ax.hist(d, bins=np.arange(0, 82, 2.5), color=PALETA["densidad"][3], ec="white", lw=0.4)
    ax.axvline(lim["alta_densidade"] / 1000, color=TINTA, lw=0.9, ls="--")
    ax.text(lim["alta_densidade"] / 1000 + 1, ax.get_ylim()[1] * 0.92, f"P75 = {num(lim['alta_densidade'])}\nalta densidad",
            fontsize=6.5, va="top")
    ax.set_xlabel("Densidad (miles de hab./km²)")
    ax.set_ylabel("Secciones")
    return v.guardar(fig, "graf_densidad.png")


# ------------------------------------------------------------------ cobertura
def cobertura(base, mun):
    s = base.secciones
    cortes = [0, 1e-9, 5, 25, 50, 75, 100.0001]
    colores = PALETA["sin_cobertura"]
    etq = ["0 % (cobertura total)", "0 – 5 %", "5 – 25 %", "25 – 50 %", "50 – 75 %", "≥ 75 %"]
    c = col(s.pct_sem_cobertura_400m, cortes, colores)
    mapa_simple(base, c, list(zip(colores, etq)), "Población estimada sin parada\na ≤ 400 m de recorrido (%)",
                "mapa_cobertura.png")
    fig, ax = plt.subplots(figsize=(80 * MM, 30 * MM))
    vals = [mun["pct_coberta_400m"], mun["pct_sem_cobertura_400m"], mun["pct_nao_determinada"]]
    cols = [PALETA["servicio"][4], PALETA["sin_cobertura"][4], "#9AA3AB"]
    izq = 0
    for val, c_ in zip(vals, cols):
        ax.barh(0, val, left=izq, color=c_, height=0.55)
        izq += val
    ax.text(vals[0] / 2, 0, f"{num(vals[0], 2)} % con parada", color="white", ha="center", va="center", fontsize=7.5, fontweight="semibold")
    ax.annotate(f"{num(vals[1], 2)} % sin parada", (vals[0] + vals[1] / 2, -0.3), (88, -0.75), fontsize=6.8, ha="right",
                arrowprops=dict(arrowstyle="-", color=SUAVE, lw=0.6))
    ax.annotate(f"{num(vals[2], 2)} % no determinada", (99.98, 0.3), (99, 0.85), fontsize=6.8, ha="right",
                arrowprops=dict(arrowstyle="-", color=SUAVE, lw=0.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(-1, 1.1)
    ax.set_axis_off()
    return v.guardar(fig, "graf_cobertura.png")


# ------------------------------------------------------------------ líneas y frecuencia
def servicio(base, lim):
    s = base.secciones
    sinc = "#E3E3E0"
    cortes = [0, 1, 2, 3, 5, 8, 1e9]
    etq = ["< 1", "1 – 2", "2 – 3", "3 – 5", "5 – 8", "≥ 8"]
    c = col(s.linhas_cob_manha, cortes, PALETA["servicio"], sinc)
    mapa_simple(base, c, list(zip(PALETA["servicio"], etq)) + [(sinc, "Sin población con parada")],
                "Líneas distintas accesibles, 07–09\n(media entre la población con parada)", "mapa_lineas.png")
    cortes = [0, 10, lim["baixa_frequencia"], 25, 40, 60, 1e9]
    etq = ["< 10", f"10 – {num(lim['baixa_frequencia'], 1)} (P25)", f"{num(lim['baixa_frequencia'], 1)} – 25", "25 – 40", "40 – 60", "≥ 60"]
    c = col(s.partidas_h_cob_manha, cortes, PALETA["servicio"], sinc)
    mapa_simple(base, c, list(zip(PALETA["servicio"], etq)) + [(sinc, "Sin población con parada")],
                "Salidas programadas accesibles por hora, 07–09\n(viajes sin duplicar; población con parada)",
                "mapa_frecuencia.png")
    for campo, umbral, xl, paso, nombre in (("linhas_cob_manha", lim["baixa_diversidade_linhas"], "Líneas distintas accesibles (07–09)", 0.5, "graf_lineas.png"),
                                           ("partidas_h_cob_manha", lim["baixa_frequencia"], "Salidas/h accesibles (07–09)", 5, "graf_frecuencia.png")):
        fig, ax = plt.subplots(figsize=(80 * MM, 48 * MM))
        x = s[campo].dropna()
        ax.hist(x, bins=np.arange(0, x.max() + paso, paso), color=PALETA["servicio"][3], ec="white", lw=0.3)
        ax.axvline(umbral, color=TINTA, ls="--", lw=0.8)
        ax.text(umbral, ax.get_ylim()[1] * 0.97, f" P25 = {num(umbral, 2 if paso < 1 else 1)}", fontsize=6.6, va="top")
        ax.set_xlabel(xl + " — población con parada", fontsize=7)
        ax.set_ylabel("Secciones", fontsize=7)
        v.guardar(fig, nombre)


# ------------------------------------------------------------------ periodos
def periodos(base, sint):
    s = base.secciones
    cortes = [-1e9, -40, -25, -10, 10, 25, 1e9]
    colores = [PALETA["variacion"][i] for i in (0, 1, 2, 3, 4, 6)]
    etq = ["≤ −40 %", "−40 a −25 %", "−25 a −10 %", "−10 a +10 %", "+10 a +25 %", "> +25 %"]
    c = col(s.var_pct_tarde_manha, cortes, colores, "#C9CED3")
    mapa_simple(base, c, list(zip(colores, etq)) + [("#C9CED3", "Sin salidas por la mañana")],
                "Variación de las salidas/h accesibles\ntarde (17–19) frente a mañana (07–09)", "mapa_variacion.png")
    orden = ["manha", "meio_dia", "tarde"]
    sint = sint.set_index("periodo").loc[orden]
    fig, axs = plt.subplots(1, 3, figsize=(104 * MM, 58 * MM))
    datos = [("media_partidas_hora", "Salidas/h accesibles\n(residente medio)", 1),
             ("media_linhas", "Líneas accesibles\n(residente medio)", 2),
             ("viagens_rede", "Viajes en la red\n(≥ 1 salida en la franja)", 0)]
    for ax, (campo, tit, dec) in zip(axs, datos):
        vals = sint[campo].astype(float).values
        b = ax.bar(range(3), vals, color=[PALETA["periodos"][p] for p in orden], width=0.62)
        for r, val in zip(b, vals):
            ax.text(r.get_x() + r.get_width() / 2, val, num(val, dec), ha="center", va="bottom", fontsize=6.6, fontweight="semibold")
        ax.set_xticks(range(3), ["07–09", "12–14", "17–19"], fontsize=6.4)
        ax.set_title(tit, fontsize=6.8)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_ylim(0, vals.max() * 1.18)
    fig.tight_layout(w_pad=1.2)
    return v.guardar(fig, "graf_periodos.png")


# ------------------------------------------------------------------ densidad x oferta
def dispersion(base, lim, mun):
    s = base.secciones.copy()
    s["d"] = s.densidade_ine_hab_km2 / 1000
    fig, axs = plt.subplots(1, 3, figsize=(172 * MM, 62 * MM))
    paneles = [("pct_coberta_400m", "Población con parada a ≤ 400 m (%)", mun["pct_coberta_400m"], "media municipal"),
               ("linhas_cob_manha", "Líneas accesibles 07–09 (con parada)", lim["baixa_diversidade_linhas"], "P25"),
               ("partidas_h_cob_manha", "Salidas/h accesibles 07–09 (con parada)", lim["baixa_frequencia"], "P25")]
    for ax, (campo, yl, ref, etq) in zip(axs, paneles):
        fondo = s[~s.prioritaria.astype(bool)]
        ax.scatter(fondo.d, fondo[campo], s=5, c="#C3C8CD", lw=0)
        for t in TIP_ORDEN[:4]:
            x = s[s.tipologia == t]
            ax.scatter(x.d, x[campo], s=11, c=PALETA["tipologia"][t], lw=0.3, ec="white", zorder=3)
        ax.axvline(lim["alta_densidade"] / 1000, color=TINTA, lw=0.7, ls="--")
        ax.axhline(ref, color=SUAVE, lw=0.6, ls=":")
        ax.text(78, ref, etq, fontsize=5.8, color=SUAVE, ha="right", va="top",
                bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.8))
        r = s[["d", campo]].corr(method="spearman").iloc[0, 1]
        ax.set_title(f"{yl}\nSpearman = {num(r, 2)}", fontsize=7.2)
        ax.set_xlabel("Densidad (miles hab./km²)", fontsize=7)
        ax.tick_params(labelsize=6.5)
    handles = [Line2D([], [], marker="o", ls="", ms=4, color=PALETA["tipologia"][t], label=PALETA["tipologia_etiqueta"][t]) for t in TIP_ORDEN[:4]]
    handles.append(Line2D([], [], marker="o", ls="", ms=4, color="#C3C8CD", label="Resto de secciones"))
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=6.6, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.06, 1, 1), w_pad=1.6)
    return v.guardar(fig, "graf_dispersion.png")


# ------------------------------------------------------------------ tipología y distritos
def tipologia(base):
    s = base.secciones
    tips = TIP_ORDEN[:4]
    n = [int((s.tipologia == t).sum()) for t in tips]
    p = [int(s.loc[s.tipologia == t, "pob_ine"].sum()) for t in tips]
    fig, axs = plt.subplots(1, 2, figsize=(120 * MM, 40 * MM), sharey=True)
    etq = [PALETA["tipologia_etiqueta"][t] for t in tips]
    for ax, vals, tit, f in ((axs[0], n, "Secciones", lambda x: num(x)), (axs[1], p, "Población INE 2024", lambda x: num(x))):
        b = ax.barh(range(4), vals, color=[PALETA["tipologia"][t] for t in tips], height=0.62)
        for r, val in zip(b, vals):
            ax.text(val, r.get_y() + r.get_height() / 2, " " + f(val), va="center", fontsize=6.8)
        ax.set_title(tit, fontsize=7.6)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)
        ax.set_xlim(0, max(vals) * 1.3)
    axs[0].set_yticks(range(4), etq, fontsize=6.8)
    axs[0].invert_yaxis()
    fig.tight_layout(w_pad=1)
    v.guardar(fig, "graf_tipologia.png")

    d = base.distritos.sort_values("cdis")
    fig, ax = plt.subplots(figsize=(84 * MM, 56 * MM))
    izq = np.zeros(len(d))
    for t, campo in zip(tips, ["tipo_a", "tipo_b", "tipo_c", "tipo_d"]):
        vals = d[campo].values.astype(float)
        ax.barh(range(len(d)), vals, left=izq, color=PALETA["tipologia"][t], height=0.66)
        izq += vals
    for i, (tot, pob) in enumerate(zip(izq, d.pob_ine_prioritarias)):
        if tot:
            ax.text(tot + 0.15, i, f"{int(tot)} · {num(pob)} hab.", va="center", fontsize=6.2)
    ax.set_yticks(range(len(d)), [f"{c} {v.DISTRITOS[c]}" for c in d.cdis], fontsize=6.4)
    ax.invert_yaxis()
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_xlim(0, izq.max() * 1.8)
    ax.set_title("Secciones prioritarias por distrito y tipo", fontsize=7.6, loc="left")
    return v.guardar(fig, "graf_distritos.png")


# ------------------------------------------------------------------ mapa de prioritarias
def prioritarias(base):
    s = base.secciones
    fig, ax = plt.subplots(figsize=(172 * MM, 152 * MM))
    v.mapa_base(ax, base, etiquetas_distrito=False)
    secc_plot(ax, s, s.tipologia.map(PALETA["tipologia"]).tolist())
    pri = s[s.prioritaria == 1]
    pri.boundary.plot(ax=ax, color=pri.tipologia.map(PALETA["tipologia"]), lw=1.6, zorder=8)   # realce: secciones pequeñas
    top = s[s.ranking <= 10]
    desp = {1: (-30, 16), 7: (-34, -2), 2: (-38, -22), 3: (-16, -34), 5: (22, -26)}
    for _, r in top.iterrows():
        p = r.geometry.representative_point()
        ax.annotate(str(int(r.ranking)), (p.x, p.y), xytext=desp.get(int(r.ranking), (8, 8)), textcoords="offset points", fontsize=6.6,
                    fontweight="bold", color=TINTA, zorder=11,
                    bbox=dict(boxstyle="circle,pad=0.18", fc="white", ec=TINTA, lw=0.5),
                    arrowprops=dict(arrowstyle="-", color=TINTA, lw=0.5))
    for _, d in base.distritos.iterrows():
        p = d.geometry.representative_point()
        ax.text(p.x, p.y - 350, d.cdis, fontsize=6.5, color=SUAVE, ha="center", zorder=9, fontweight="semibold")
    items = [(PALETA["tipologia"][t], PALETA["tipologia_etiqueta"][t] + f" ({int((s.tipologia == t).sum())})") for t in TIP_ORDEN]
    v.leyenda(ax, items, "Clasificación (franja 07–09)", loc="lower right")
    v.escala_norte(ax)
    return v.guardar(fig, "mapa_prioritarias.png")


# ------------------------------------------------------------------ detalle de las primeras
def detalle(base):
    s = base.secciones
    pts = v.cargar("puntos_demanda")
    par = v.cargar("paradas_autobus")
    red = v.cargar("red_peatonal", v.CONTEXTO)
    zonas = [("Triana y Los Remedios — falta de parada cercana", ["4109106003", "4109111012", "4109111014", "4109111011", "4109106036"]),
             ("Cerro-Amate — parada cercana con pocas salidas", ["4109104054", "4109104065", "4109104049"])]
    fig, axs = plt.subplots(1, 2, figsize=(172 * MM, 86 * MM))
    for ax, (tit, cod) in zip(axs, zonas):
        foco = s[s.cusec.isin(cod)]
        x0, y0, x1, y1 = foco.total_bounds
        cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) / 2 + 450
        ext = (cx - r * 1.15, cy - r, cx + r * 1.15, cy + r)
        v.mapa_base(ax, base, ext=ext, distritos=False, limite=False)
        red.cx[ext[0]:ext[2], ext[1]:ext[3]].query("utilizable == 1").plot(ax=ax, color="#C9CED3", lw=0.35, zorder=3)
        sub = s.cx[ext[0]:ext[2], ext[1]:ext[3]]
        sub.plot(ax=ax, color="white", ec="#B9BEC4", lw=0.3, zorder=2)
        sp = sub[sub.prioritaria == 1]
        sp.plot(ax=ax, color=sp.tipologia.map(PALETA["tipologia"]), alpha=0.18, lw=0, zorder=2.5)
        foco.boundary.plot(ax=ax, color=foco.tipologia.map(PALETA["tipologia"]), lw=1.4, zorder=5)
        puestos = []
        for _, rr in foco.sort_values("ranking").iterrows():
            if rr.ranking <= 15:
                p = rr.geometry.representative_point()
                x, y = p.x, p.y
                while any(abs(x - a) < 160 and abs(y - b) < 160 for a, b in puestos):   # evita rótulos superpuestos
                    y -= 190
                puestos.append((x, y))
                ax.text(x, y, str(int(rr.ranking)), fontsize=7, fontweight="bold", ha="center", va="center", zorder=12,
                        bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec=TINTA, lw=0.5))
        pp = pts.cx[ext[0]:ext[2], ext[1]:ext[3]]
        colp = pp.situacion_400m.map({"coberto_400m": PALETA["servicio"][4], "sem_cobertura_400m": PALETA["tipologia"]["A_baixa_cobertura"],
                                      "nao_determinado": "#9AA3AB"})
        ax.scatter(pp.geometry.x, pp.geometry.y, s=3 + pp.pob_estimada / 40, c=colp, ec="white", lw=0.4, zorder=7, alpha=0.9)
        pa = par.cx[ext[0]:ext[2], ext[1]:ext[3]]
        ax.scatter(pa.geometry.x, pa.geometry.y, s=5 + pa.salidas_h_manana * 0.7, marker="s", c="white", ec=TINTA, lw=0.7, zorder=8)
        ax.set_title(tit, fontsize=7.6, loc="left")
        ax.set_xlim(ext[0], ext[2])
        ax.set_ylim(ext[1], ext[3])
        v.escala_norte(ax, km=1 if ext[2] - ext[0] > 2600 else 0.5)
    h = [Line2D([], [], marker="o", ls="", ms=5, color=PALETA["servicio"][4], label="Punto de demanda con parada a ≤ 400 m"),
         Line2D([], [], marker="o", ls="", ms=5, color=PALETA["tipologia"]["A_baixa_cobertura"], label="Punto sin parada a ≤ 400 m"),
         Line2D([], [], marker="s", ls="", ms=5, mfc="white", mec=TINTA, label="Parada (tamaño = salidas/h 07–09)"),
         Line2D([], [], color="#C9CED3", lw=1.2, label="Red peatonal")]
    fig.legend(handles=h, loc="lower center", ncol=4, fontsize=6.4, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.05, 1, 1), w_pad=1.0)
    return v.guardar(fig, "mapa_detalle.png")


# ------------------------------------------------------------------ ranking (33)
def ranking(base):
    s = base.secciones[base.secciones.prioritaria == 1].sort_values("ranking")
    fig, ax = plt.subplots(figsize=(84 * MM, 112 * MM))
    y = np.arange(len(s))
    ax.hlines(y, 0, s.partidas_h_manha, color="#D5D9DD", lw=0.8)
    ax.scatter(s.partidas_h_manha, y, s=12 + s.pob_sem_oferta_manha / 6, c=s.tipologia.map(PALETA["tipologia"]), ec="white", lw=0.4, zorder=3)
    ax.set_yticks(y, [f"{int(r)}  {c}" for r, c in zip(s.ranking, s.cusec)], fontsize=6.2)
    ax.invert_yaxis()
    ax.set_xlabel("Salidas/h accesibles 07–09 (residente medio; sin parada = 0)", fontsize=6.6)
    ax.tick_params(axis="x", labelsize=6.4)
    ax.set_title("Las 33 secciones prioritarias por orden de ranking\n(tamaño = población estimada sin oferta a 07–09)",
                 fontsize=7.2, loc="left")
    return v.guardar(fig, "graf_ranking.png")


def main():
    v.configurar_fuentes()
    base = v.Base()
    lim = {r.criterio: r.valor for r in pd.read_csv(v.caminho("resultados/etapa4/limiares.csv")).query("cenario == 'principal'").itertuples()}
    mun = {r.indicador: r.valor for r in pd.read_csv(v.caminho("resultados/etapa2/sintese_municipal.csv")).itertuples()}
    sint = pd.read_csv(v.caminho("resultados/etapa3/sintese_municipal_periodo.csv"))
    for f in (lambda: portada(base), lambda: localizacion(base), lambda: densidad(base, lim), lambda: cobertura(base, mun),
              lambda: servicio(base, lim), lambda: periodos(base, sint), lambda: dispersion(base, lim, mun),
              lambda: tipologia(base), lambda: prioritarias(base), lambda: detalle(base), lambda: ranking(base)):
        f()
    print(f"  {len(list(v.FIGURAS.glob('*.png')))} figuras en {v.FIGURAS.relative_to(v.caminho('.'))}")


if __name__ == "__main__":
    main()
