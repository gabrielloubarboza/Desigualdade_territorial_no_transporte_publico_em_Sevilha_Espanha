"""Etapa 5 — Proyecto QGIS con los mapas del informe como diseños de impresión (produtos/sevilla_oferta_bus.qgz).

Uso:  .venv\\Scripts\\python.exe scripts\\22_proyecto_qgis.py [--exportar[=<carpeta>]]

1. Reproduce en memoria los mapas de 17_figuras.py (no escribe ningún PNG) y mide su geometría tal como la
   guarda matplotlib: tamaño de la página recortada, posición y extensión de cada mapa, leyendas, textos,
   escala gráfica y flecha de norte, clases y colores.
2. Con el Python de QGIS, scripts/qgis_proyecto_layouts.py arma el proyecto: capas de los dos GeoPackages de
   produtos/ (rutas relativas), un grupo y un tema de mapa por figura y un diseño de impresión por mapa.
Con --exportar, los diseños se exportan a PNG (220 ppp), por defecto en produtos/figuras_qgis/, para compararlos.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile

import matplotlib.colors as mcolors
from matplotlib.text import Annotation, Text
from matplotlib.transforms import Bbox

from comum import caminho

QGIS_PYTHON = os.environ.get("QGIS_PYTHON", r"C:\Program Files\QGIS 3.40.8\bin\python-qgis-ltr.bat")
PROYECTO = caminho("produtos/sevilla_oferta_bus.qgz")
EXPORT = caminho("produtos/figuras_qgis")
MAPAS = ["portada.png", "mapa_localizacion.png", "mapa_densidad.png", "mapa_cobertura.png", "mapa_lineas.png",
         "mapa_frecuencia.png", "mapa_variacion.png", "mapa_prioritarias.png", "mapa_detalle.png"]
MM = 25.4


def cargar(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, caminho(f"scripts/{archivo}"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


def hexa(c):
    return None if c is None or (not isinstance(c, str) and len(c) == 4 and c[3] == 0) else mcolors.to_hex(c)


class Medidor:
    """Sustituye visual.guardar/clasificar/leyenda/escala_norte para registrar la figura en lugar de guardarla."""

    def __init__(self, v):
        self.v, self.figuras, self._clases, self._leyendas, self._escala = v, [], [], [], {}
        self.orig = {k: getattr(v, k) for k in ("guardar", "clasificar", "leyenda", "escala_norte")}
        v.guardar, v.clasificar, v.leyenda, v.escala_norte = self.guardar, self.clasificar, self.leyenda, self.escala_norte

    def clasificar(self, serie, cortes, colores):
        self._clases.append({"cortes": [float(c) for c in cortes], "colores": list(colores)})
        return self.orig["clasificar"](serie, cortes, colores)

    def leyenda(self, ax, items, titulo=None, **kw):
        self._leyendas.append({"items": [[c, e] for c, e in items], "titulo": titulo})
        return self.orig["leyenda"](ax, items, titulo, **kw)

    def escala_norte(self, ax, *a, **k):
        nt, npch = len(ax.texts), len(ax.patches)
        self.orig["escala_norte"](ax, *a, **k)
        self._escala[id(ax)] = (nt, len(ax.texts), npch, len(ax.patches))

    def guardar(self, fig, nombre, recortar=True):
        clases, leyendas, escala = self._clases, self._leyendas, self._escala
        self._clases, self._leyendas, self._escala = [], [], {}
        if nombre in MAPAS:
            self.figuras.append(medir(fig, nombre, recortar, clases, leyendas, escala))
        self.v.plt.close(fig)
        return self.v.FIGURAS / nombre


def medir(fig, nombre, recortar, clases, leyendas, escala):
    fig.set_dpi(220)   # resolución de guardado: medidas de texto sin el redondeo a píxeles de 100 ppp
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    dpi = fig.dpi
    w, h = fig.get_size_inches()
    bb = fig.get_tightbbox(r).padded(0.03) if recortar else Bbox.from_bounds(0, 0, w, h)   # como savefig

    def caja(b):
        x0, y0, x1, y1 = b.x0 / dpi, b.y0 / dpi, b.x1 / dpi, b.y1 / dpi
        return [(x0 - bb.x0) * MM, (bb.y1 - y1) * MM, (x1 - x0) * MM, (y1 - y0) * MM]

    def punto(xd, yd):
        return [(xd / dpi - bb.x0) * MM, (bb.y1 - yd / dpi) * MM]

    def texto(t, ax, tipo):
        b = Text.get_window_extent(t, r)   # en una Annotation, solo el texto (sin la línea de llamada)
        rot = t.get_rotation()
        if rot:
            t.set_rotation(0)
            b0 = Text.get_window_extent(t, r)
            t.set_rotation(rot)
        else:
            b0 = b
        salto = None
        if "\n" in t.get_text():   # distancia entre líneas: alto total menos alto de una línea
            s0 = t.get_text()
            t.set_text(s0.split("\n")[0])
            una = Text.get_window_extent(t, r).height
            t.set_text(s0)
            salto = (b0.height - una) / dpi * 72 / (s0.count("\n"))
        caja_rot = caja(b)
        cx, cy = (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
        d = {"tipo": tipo, "texto": t.get_text(), "caja": caja_rot, "ancho": b0.width / dpi * MM, "alto": b0.height / dpi * MM,
             "rot": rot, "size": t.get_fontsize(), "weight": t.get_fontweight(), "style": t.get_style(),
             "color": hexa(t.get_color()), "ha": t.get_ha(), "va": t.get_va(), "salto_pt": salto,
             "centro_datos": [float(c) for c in ax.transData.inverted().transform((cx, cy))]}
        if isinstance(t, Annotation):
            d["ancla_datos"] = [float(c) for c in t.xy]
        p = t.get_bbox_patch()
        if p is not None:
            bs = p.get_boxstyle()
            d["fondo"] = {"estilo": type(bs).__name__.lower(), "pad": getattr(bs, "pad", 0.3), "fc": hexa(p.get_facecolor()),
                          "ec": hexa(p.get_edgecolor()) if p.get_linewidth() else None, "lw": p.get_linewidth(),
                          "alpha": p.get_alpha() if p.get_alpha() is not None else 1.0}
        return d

    def med_leyenda(lg):
        """Caja de la leyenda, paso entre filas y separación título–primera fila (mm)."""
        cajas = [caja(t.get_window_extent(r)) for t in lg.get_texts()]
        centros = [c[1] + c[3] / 2 for c in cajas]
        paso = (centros[-1] - centros[0]) / (len(centros) - 1) if len(centros) > 1 and centros[-1] != centros[0] else None
        tit = lg.get_title()
        sep = None
        if tit.get_text():
            ct = caja(tit.get_window_extent(r))
            sep = centros[0] - (ct[1] + ct[3] / 2)
        return {"caja": caja(lg.get_window_extent(r)), "paso": paso, "sep_titulo": sep}

    ejes = []
    for ax in fig.axes:
        e0 = escala.get(id(ax))
        textos = []
        for i, t in enumerate(ax.texts):
            if not t.get_text() or not t.get_visible():
                continue
            if e0 and e0[0] <= i < e0[1]:
                tipo = "escala"
            elif isinstance(t, Annotation):
                tipo = "anotacion"
            elif t.get_transform() == ax.transData:
                tipo = "datos"
            else:
                tipo = "ejes"
            textos.append(texto(t, ax, tipo))
        for tit in (ax.title, ax._left_title, ax._right_title):   # set_title(loc="left") usa _left_title
            if tit.get_text():
                textos.append(texto(tit, ax, "titulo"))
        parches = []
        if e0:
            for p in ax.patches[e0[2]:e0[3]]:
                verts = p.get_transform().transform(p.get_path().vertices)
                parches.append({"vertices": [punto(x, y) for x, y in verts], "fc": hexa(p.get_facecolor()),
                                "ec": hexa(p.get_edgecolor()), "lw": p.get_linewidth()})
        lg = ax.get_legend()
        ejes.append({"caja": caja(ax.bbox), "xlim": [float(x) for x in ax.get_xlim()], "ylim": [float(y) for y in ax.get_ylim()],
                     "eje_visible": bool(ax.axison), "marco": hexa(ax.spines["left"].get_edgecolor()) if ax.axison else None,
                     "marco_lw": ax.spines["left"].get_linewidth() if ax.axison else 0,
                     "textos": textos, "escala": parches, "leyenda": med_leyenda(lg) if lg else None})
    leyendas_fig = [{**med_leyenda(lg), "ncol": lg._ncols, "items": [t.get_text() for t in lg.get_texts()]} for lg in fig.legends]
    return {"nombre": nombre, "pagina": [bb.width * MM, bb.height * MM], "fondo": hexa(fig.get_facecolor()),
            "ejes": ejes, "leyendas": leyendas, "leyendas_figura": leyendas_fig, "clases": clases}


def zonas_detalle(f17):
    """Secciones destacadas en cada panel de mapa_detalle (lista `zonas` de 17_figuras.detalle)."""
    for nodo in ast.walk(ast.parse(inspect.getsource(f17.detalle))):
        if isinstance(nodo, ast.Assign) and getattr(nodo.targets[0], "id", None) == "zonas":
            return ast.literal_eval(nodo.value)
    raise RuntimeError("No se encontró `zonas` en 17_figuras.detalle")


def main():
    sys.path.insert(0, str(caminho("scripts")))
    v = cargar("visual", "visual.py")
    med = Medidor(v)
    f17 = cargar("figuras17", "17_figuras.py")
    f17.main()   # guardar está interceptado: no se escribe ningún archivo
    geo = {"figuras": med.figuras, "paleta": v.PALETA, "zonas_detalle": zonas_detalle(f17),
           "tip_orden": v.TIP_ORDEN, "distritos": v.DISTRITOS}
    print(f"  {len(med.figuras)} mapas medidos: " + ", ".join(f["nombre"] for f in med.figuras))
    if not os.path.exists(QGIS_PYTHON):
        raise SystemExit(f"QGIS no encontrado en {QGIS_PYTHON} (variable QGIS_PYTHON)")
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "geometria_mapas.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(geo, f, ensure_ascii=False)
        args = [QGIS_PYTHON, str(caminho("scripts/qgis_proyecto_layouts.py")), ruta, str(PROYECTO)]
        for a in sys.argv[1:]:
            if a.startswith("--exportar"):
                args.append(a.split("=", 1)[1] if "=" in a else str(EXPORT))
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit("Fallo al construir el proyecto QGIS")


if __name__ == "__main__":
    main()
