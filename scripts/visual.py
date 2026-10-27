"""Identidad visual compartida (Etapa 5): paleta, tipografía, mapa base y formato numérico en español.

Las figuras leen los GeoPackages finales de produtos/ — no necesitan el banco PostgreSQL.
"""
from __future__ import annotations

import json

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrow, Patch, Rectangle  # noqa: E402

from comum import caminho  # noqa: E402

PALETA = json.loads(caminho("config/paleta.json").read_text(encoding="utf-8"))
TINTA, SUAVE, FINA = PALETA["tinta"], PALETA["tinta_suave"], PALETA["linea_fina"]
TIP_ORDEN = ["A_baixa_cobertura", "B_baixa_diversidade_linhas", "C_baixa_frequencia", "D_deficiencias_combinadas",
             "alta_densidade_sem_deficiencia", "fora_alta_densidade"]
RESULTADOS = caminho("produtos/sevilla_oferta_bus_resultados.gpkg")
CONTEXTO = caminho("produtos/sevilla_oferta_bus_contexto_osm.gpkg")
FIGURAS = caminho("produtos/figuras")
DISTRITOS = {"01": "Casco Antiguo", "02": "Macarena", "03": "Nervión", "04": "Cerro-Amate", "05": "Sur",
             "06": "Triana", "07": "Norte", "08": "San Pablo-Santa Justa", "09": "Este-Alcosa-Torreblanca",
             "10": "Bellavista-La Palmera", "11": "Los Remedios"}


def configurar_fuentes():
    for f in caminho("assets/fonts").glob("*.ttf"):
        font_manager.fontManager.addfont(str(f))
    plt.rcParams.update({
        "font.family": "IBM Plex Sans", "font.size": 8, "axes.edgecolor": FINA, "axes.labelcolor": TINTA,
        "axes.titlesize": 9, "axes.titleweight": "semibold", "axes.titlecolor": TINTA, "xtick.color": SUAVE,
        "ytick.color": SUAVE, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "legend.frameon": False, "figure.dpi": 100, "savefig.dpi": 220, "text.color": TINTA,
    })


def num(x, dec=0):
    """Formato español: miles con punto, decimales con coma."""
    if x is None:
        return "—"
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def cargar(capa, gpkg=RESULTADOS):
    return gpd.read_file(gpkg, layer=capa)


class Base:
    """Capas de contexto cargadas una sola vez."""

    def __init__(self):
        self.limite = cargar("limite_municipal")
        self.distritos = cargar("distritos")
        self.secciones = cargar("secciones_indicadores")
        bar = cargar("barreras_poligonos", CONTEXTO)
        x0, y0, x1, y1 = self.limite.total_bounds
        m = 900
        self.ext = (x0 - m, y0 - m, x1 + m, y1 + m)
        self.agua = bar[bar.clase == "agua"].cx[x0 - 3000:x1 + 3000, y0 - 3000:y1 + 3000]


def mapa_base(ax, base, ext=None, distritos=True, etiquetas_distrito=False, agua=True, limite=True):
    ext = ext or base.ext
    ax.set_xlim(ext[0], ext[2])
    ax.set_ylim(ext[1], ext[3])
    ax.set_aspect("equal")
    ax.set_axis_off()
    if agua:
        base.agua.plot(ax=ax, color=PALETA["agua"], lw=0, zorder=4)
    if distritos:
        base.distritos.boundary.plot(ax=ax, color=TINTA, lw=0.55, zorder=6)
    if limite:
        base.limite.boundary.plot(ax=ax, color=TINTA, lw=0.9, zorder=7)
    if etiquetas_distrito:
        for _, d in base.distritos.iterrows():
            p = d.geometry.representative_point()
            ax.text(p.x, p.y, f"{d.cdis}", fontsize=7, fontweight="semibold", color=TINTA, ha="center", va="center",
                    zorder=9, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))


def escala_norte(ax, km=2, pos=(0.20, 0.035), color=None):
    color = color or TINTA
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + pos[0] * (x1 - x0)
    y = y0 + pos[1] * (y1 - y0)
    h = (y1 - y0) * 0.008
    for i in range(2):
        ax.add_patch(Rectangle((x + i * km * 500, y), km * 500, h, fc=color if i == 0 else "white", ec=color, lw=0.6, zorder=10))
    ax.text(x, y + 2.2 * h, "0", fontsize=6, ha="center", color=color, zorder=10)
    ax.text(x + km * 1000 + (x1 - x0) * 0.008, y - 0.3 * h, f"{num(km, 1 if km % 1 else 0)} km", fontsize=6, ha="left",
            va="bottom", color=color, zorder=10)
    xn, yn = x1 - 0.05 * (x1 - x0), y1 - 0.11 * (y1 - y0)
    ax.add_patch(FancyArrow(xn, yn, 0, 0.05 * (y1 - y0), width=(x1 - x0) * 0.004, head_width=(x1 - x0) * 0.018,
                            head_length=(y1 - y0) * 0.022, color=color, zorder=10, length_includes_head=True))
    ax.text(xn, yn - 0.018 * (y1 - y0), "N", fontsize=7, fontweight="semibold", ha="center", va="top", color=color, zorder=10)


def leyenda(ax, items, titulo=None, loc="lower right", ncol=1, fontsize=6.6, **kw):
    handles = [Patch(fc=c, ec="none" if c != "white" else FINA, label=e) for c, e in items]
    lg = ax.legend(handles=handles, title=titulo, loc=loc, ncol=ncol, fontsize=fontsize, title_fontsize=fontsize + 0.4,
                   handlelength=1.3, handleheight=0.9, borderaxespad=0.6, labelspacing=0.35, **kw)
    lg.get_title().set_fontweight("semibold")
    lg._legend_box.align = "left"
    return lg


def clasificar(serie, cortes, colores):
    """Asigna colores por intervalos [c_i, c_{i+1}); devuelve lista de colores (None para nulos)."""
    out = []
    for v in serie:
        if v is None or v != v:
            out.append(None)
            continue
        for i in range(len(cortes) - 1):
            if cortes[i] <= v < cortes[i + 1]:
                out.append(colores[i])
                break
        else:
            out.append(colores[-1])
    return out


def guardar(fig, nombre, recortar=True):
    FIGURAS.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURAS / nombre, bbox_inches="tight" if recortar else None, pad_inches=0.03, facecolor=fig.get_facecolor())
    plt.close(fig)
    return FIGURAS / nombre
