"""Etapa 5 — Verificación de los productos finales y del contenido publicable.

Uso:  .venv\\Scripts\\python.exe scripts\\20_verificacion_productos.py [--sin-bd]

Comprueba PDF, figuras, GeoPackages (capas, CRS, geometrías y, si hay banco, atributos frente a PostgreSQL),
números del README, enlaces relativos, fragmentos de docs/codigo_em_destaque.md, conjunto de archivos publicables
según .gitignore (con un repositorio git temporal FUERA del proyecto) y ausencia de credenciales o rutas personales.
Resultado en docs/verificacion_productos.md (y en qa.resultado_testes con prefijo H si hay banco).
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from pypdf import PdfReader

from comum import RAIZ, caminho, carregar_config

CFG = carregar_config()
SIN_BD = "--sin-bd" in sys.argv
RES: list[tuple] = []
PDF = caminho("produtos/informe_sevilla_oferta_autobuses.pdf")
GPKG_R = caminho("produtos/sevilla_oferta_bus_resultados.gpkg")
GPKG_C = caminho("produtos/sevilla_oferta_bus_contexto_osm.gpkg")
FIGURAS = ["portada", "mapa_localizacion", "mapa_densidad", "graf_densidad", "mapa_cobertura", "graf_cobertura",
           "mapa_lineas", "graf_lineas", "mapa_frecuencia", "graf_frecuencia", "mapa_variacion", "graf_periodos",
           "graf_dispersion", "graf_tipologia", "graf_distritos", "mapa_prioritarias", "mapa_detalle", "graf_ranking"]


def reg(tid, desc, status, det):
    RES.append((tid, "Productos", desc, status, det))
    print(f"[{status:9}] {tid} {desc} — {det}")


def n(x, dec=0):
    s = f"{abs(float(x)):,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return ("−" + s) if float(x) < 0 else s


def esperados():
    r = caminho("resultados")
    m2 = {x.indicador: x.valor for x in pd.read_csv(r / "etapa2/sintese_municipal.csv").itertuples()}
    s3 = pd.read_csv(r / "etapa3/sintese_municipal_periodo.csv").set_index("periodo")
    lim = {x.criterio: x.valor for x in pd.read_csv(r / "etapa4/limiares.csv").query("cenario == 'principal'").itertuples()}
    m4 = pd.read_csv(r / "etapa4/sintese_municipal.csv").query("cenario == 'principal'").set_index("indicador")
    return {
        "cobertura": f"{n(m2['pct_coberta_400m'], 2)} %", "sin_parada": f"{n(m2['pct_sem_cobertura_400m'], 2)} %",
        "pob_ine": n(686741), "pob_grade": n(m2["populacao_grade_estimada_sevilla"]),
        "pob_cubierta": n(m2["populacao_coberta_400m"]), "pob_sin": n(m2["populacao_sem_cobertura_400m"]),
        "umbral_dens": n(lim["alta_densidade"], 1), "umbral_lin": n(lim["baixa_diversidade_linhas"], 2),
        "umbral_freq": n(lim["baixa_frequencia"], 2), "ph_manana": n(s3.loc["manha", "media_partidas_hora"], 1),
        "ph_tarde": n(s3.loc["tarde", "media_partidas_hora"], 1), "lin_manana": n(s3.loc["manha", "media_linhas"], 2),
        "pri_secc": n(m4.loc["secoes_prioritarias", "secoes"]), "pri_pob": n(m4.loc["secoes_prioritarias", "pob_ine"]),
        "viajes": n(s3.loc["manha", "viagens_rede"]),
    }


def v_pdf(esp):
    r = PdfReader(str(PDF))
    txt = "\n".join(p.extract_text() or "" for p in r.pages)
    txt_n = re.sub(r"\s+", " ", txt)
    faltan = [k for k, v in esp.items() if v not in txt_n]
    malos = [t for t in ("nan", "None", "{", "}", "morador", "pontualidad", "NaN") if re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", txt_n)]
    ok = len(r.pages) == 13 and not faltan and not malos and r.metadata.title
    reg("H01", "PDF legible, 13 páginas y cifras coherentes con los CSV", "OK" if ok else "FALHA",
        f"{len(r.pages)} páginas; {PDF.stat().st_size / 1e6:.1f} MB; cifras clave ausentes: {faltan or 'ninguna'}; "
        f"marcas indebidas: {malos or 'ninguna'}; título: {r.metadata.title!r}")
    return txt_n


def v_figuras():
    faltan = [f for f in FIGURAS if not (caminho("produtos/figuras") / f"{f}.png").exists()]
    peq = [f for f in FIGURAS if f not in faltan and (caminho("produtos/figuras") / f"{f}.png").stat().st_size < 10_000]
    extra = sorted(p.stem for p in caminho("produtos/figuras").glob("*.png") if p.stem not in FIGURAS)
    reg("H02", "Figuras del informe presentes", "OK" if not faltan and not peq and not extra else "FALHA",
        f"{len(FIGURAS) - len(faltan)} de {len(FIGURAS)}; vacías: {peq or 'ninguna'}; sobrantes: {extra or 'ninguna'}")


def v_gpkg():
    problemas, resumen = [], []
    for g in (GPKG_R, GPKG_C):
        meta = pyogrio.read_dataframe(g, layer="metadatos_capas")
        for capa, nreg in zip(meta.capa, meta.n_registros):
            info = pyogrio.read_info(g, layer=capa)
            gdf = gpd.read_file(g, layer=capa)
            inval = int((~gdf.geometry.is_valid).sum())
            if info["features"] != nreg or info["crs"] != "EPSG:25830" or inval:
                problemas.append(f"{capa}: n={info['features']}/{nreg} crs={info['crs']} inválidas={inval}")
            resumen.append(f"{capa} {info['features']} {info['geometry_type']}")
    estilos = pyogrio.list_layers(GPKG_R)[:, 0].tolist()
    reg("H03", "GeoPackages: capas, CRS EPSG:25830 y geometrías válidas", "OK" if not problemas else "FALHA",
        "; ".join(resumen) + f"; tabla de estilos QGIS: {'layer_styles' in estilos}; problemas: {problemas or 'ninguno'}")


def v_bd():
    if SIN_BD:
        reg("H04", "Atributos del GeoPackage frente al banco", "LIMITACAO", "no ejecutado (--sin-bd)")
        return
    from comum import conectar
    cols = ["cusec", "pob_ine", "densidade_ine_hab_km2", "pct_coberta_400m", "linhas_cob_manha", "partidas_h_manha",
            "partidas_h_tarde", "tipologia", "ranking", "prioritaria", "baixa_frequencia"]
    g = gpd.read_file(GPKG_R, layer="secciones_indicadores")[cols].sort_values("cusec").reset_index(drop=True)
    with conectar(CFG) as c:
        cur = c.execute(f"SELECT {', '.join(cols)} FROM analise.diag_resultado_seccion ORDER BY cusec")
        b = pd.DataFrame(cur.fetchall(), columns=cols)
        rk = pd.DataFrame(c.execute("SELECT cusec, ranking FROM analise.diag_resultado_seccion WHERE prioritaria").fetchall(),
                          columns=["cusec", "ranking"])
    dif = {}
    for col in cols:
        x, y = g[col], b[col]
        if col in ("cusec", "tipologia"):
            dif[col] = int((x.astype(str) != y.astype(str)).sum())
        else:
            dif[col] = int((~np.isclose(pd.to_numeric(x, errors="coerce").astype(float), pd.to_numeric(y, errors="coerce").astype(float),
                                        rtol=1e-12, atol=1e-9, equal_nan=True)).sum())
    csv = pd.read_csv(caminho("resultados/etapa4/ranking_prioritarias.csv"), dtype={"cusec": str})
    rk_ok = csv[["cusec", "ranking"]].sort_values("cusec").reset_index(drop=True).equals(rk.sort_values("cusec").reset_index(drop=True))
    tipos = g[g.prioritaria.astype(bool)].tipologia.str[0].value_counts().sort_index().to_dict()
    ok = len(g) == 521 and not any(dif.values()) and rk_ok
    reg("H04", "Atributos del GeoPackage y CSV del ranking iguales al banco", "OK" if ok else "FALHA",
        f"{len(g)} secciones; diferencias por columna: {dif}; ranking CSV = banco: {rk_ok}; prioritarias por tipo: {tipos}")


def v_readme(esp):
    t = re.sub(r"\s+", " ", caminho("README.md").read_text(encoding="utf-8"))
    claves = ["cobertura", "pob_ine", "pob_grade", "pob_cubierta", "pob_sin", "umbral_dens", "ph_manana", "ph_tarde",
              "lin_manana", "pri_secc", "pri_pob"]
    faltan = [k for k in claves if esp[k] not in t]
    reg("H05", "Cifras del README coherentes con los resultados", "OK" if not faltan else "FALHA", f"ausentes: {faltan or 'ninguna'}")


def v_enlaces():
    rotos = []
    for md in [caminho("README.md"), *caminho("docs").glob("*.md")]:
        for destino in re.findall(r"\]\(([^)\s]+)\)", md.read_text(encoding="utf-8")):
            if destino.startswith(("http", "#", "mailto:")):
                continue
            ruta = (md.parent / destino.split("#")[0]).resolve()
            if not ruta.exists():
                rotos.append(f"{md.name} → {destino}")
    for img in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", caminho("README.md").read_text(encoding="utf-8")):
        if not (RAIZ / img).exists():
            rotos.append(f"imagen {img}")
    reg("H06", "Enlaces relativos del README y de docs/", "OK" if not rotos else "FALHA", f"rotos: {rotos or 'ninguno'}")


def v_codigo():
    spec = importlib.util.spec_from_file_location("cd", caminho("scripts/19_codigo_em_destaque.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = caminho("docs/codigo_em_destaque.md").read_text(encoding="utf-8")
    desinc = []
    for _, items in mod.SECCIONES:
        for titulo, _, ruta, ini, fin in items:
            a, b, codigo = mod.extraer(ruta, ini, fin)
            if codigo not in doc or f"#L{a}-L{b}" not in doc:
                desinc.append(titulo)
    total = sum(len(i) for _, i in mod.SECCIONES)
    reg("H07", "Fragmentos de código en destaque idénticos a los archivos", "OK" if not desinc else "FALHA",
        f"{total} fragmentos; desincronizados: {desinc or 'ninguno'}")


def publicables():
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        out = subprocess.run(["git", f"--git-dir={tmp}/.git", f"--work-tree={RAIZ}", "ls-files", "--others", "--exclude-standard"],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [RAIZ / p for p in out.splitlines() if p]


def v_publicables():
    try:
        arch = publicables()
    except (OSError, subprocess.CalledProcessError) as e:
        reg("H08", "Conjunto de archivos publicables", "LIMITACAO", f"git no disponible ({e})")
        return []
    rel = [p.relative_to(RAIZ).as_posix() for p in arch]
    prohibidos = [r for r in rel if r.startswith((".venv/", "data/raw/")) and r != "data/raw/.gitkeep"
                  or "tussam_ide" in r or (r.startswith("resultados/") and r.endswith(".gpkg")) or "__pycache__" in r]
    grandes = sorted(((p.stat().st_size, p.relative_to(RAIZ).as_posix()) for p in arch), reverse=True)[:5]
    total = sum(p.stat().st_size for p in arch)
    lista = caminho("docs/arquivos_publicaveis.txt")
    lista.write_text("\n".join(sorted(rel)) + "\n", encoding="utf-8")
    reg("H08", "Conjunto publicable según .gitignore (sin datos brutos, IDE, caché ni entorno)",
        "OK" if not prohibidos and all(s < 50e6 for s, _ in grandes) else "FALHA",
        f"{len(rel)} archivos, {total / 1e6:.1f} MB; mayores: " + ", ".join(f"{r} ({s / 1e6:.1f} MB)" for s, r in grandes)
        + f"; prohibidos: {prohibidos or 'ninguno'}; lista en docs/arquivos_publicaveis.txt")
    return arch


def v_secretos(arch):
    patrones = [r"C:\\Users\\", r"C:/Users/", r"PGPASSWORD\s*=\s*\S", r"password\s*=\s*['\"]?\w", r"api[_-]?key\s*=\s*['\"]\w",
                r"[\w.]+@(hotmail|gmail|outlook|yahoo)\.", r"token\s*=\s*['\"]\w{8,}"]
    propios = {caminho("scripts/20_verificacion_productos.py"), caminho("docs/verificacion_productos.md")}   # contienen los patrones
    hallados = []
    for p in arch:
        if p.suffix.lower() in {".png", ".pdf", ".gpkg", ".ttf", ".gz"} or p in propios:
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pat in patrones:
            if re.search(pat, t, re.IGNORECASE):
                hallados.append(f"{p.relative_to(RAIZ).as_posix()}: {pat}")
    for p in (PDF, GPKG_R, GPKG_C):   # binarios: búsqueda de rutas personales en bytes
        b = p.read_bytes()
        for pat in (b"C:\\Users\\", b"C:/Users/", b"hotmail"):
            if pat in b:
                hallados.append(f"{p.name}: {pat!r}")
    reg("H09", "Sin credenciales, correos ni rutas personales en lo publicable", "OK" if not hallados else "FALHA",
        f"coincidencias: {hallados or 'ninguna'}")


def v_licencias():
    lic = caminho("LICENSE").read_text(encoding="utf-8")
    ok = "MIT License" in lic and "AUTORÍA PENDIENTE" in lic and caminho("docs/licencias_datos.md").exists() \
        and caminho("assets/fonts/LICENSE_IBM_Plex.txt").exists()
    reg("H10", "Licencia MIT del código, condiciones de datos y licencia tipográfica", "LIMITACAO" if ok else "FALHA",
        "MIT solo para código; datos según docs/licencias_datos.md; autoría pendiente de completar por el autor")


def main():
    esp = esperados()
    v_pdf(esp)
    v_figuras()
    v_gpkg()
    v_bd()
    v_readme(esp)
    v_enlaces()
    v_codigo()
    arch = v_publicables()
    v_secretos(arch)
    v_licencias()
    ejec = dt.datetime.now(dt.timezone.utc)
    if not SIN_BD:
        from comum import conectar
        with conectar(CFG) as c, c.cursor() as cur:
            cur.executemany("INSERT INTO qa.resultado_testes VALUES (%s,%s,%s,%s,%s,%s)", [(ejec, *r) for r in RES])
            c.commit()
    resumen = {s: sum(1 for r in RES if r[3] == s) for s in ("OK", "LIMITACAO", "FALHA")}
    lin = ["# Verificación de productos — Etapa 5", "",
           f"Ejecución: {ejec.isoformat(timespec='seconds')} — OK: {resumen['OK']}, LIMITACION: {resumen['LIMITACAO']}, "
           f"FALLO: {resumen['FALHA']}", "",
           "Generado por `scripts/20_verificacion_productos.py`. La revisión visual de las páginas del PDF se hizo aparte, "
           "sobre las páginas rasterizadas, y no forma parte de esta comprobación automática.", "",
           "| ID | Verificación | Estado | Detalle |", "|---|---|---|---|"]
    lin += [f"| {t} | {d} | **{s}** | {x.replace('|', '/')} |" for t, _, d, s, x in RES]
    caminho("docs/verificacion_productos.md").write_text("\n".join(lin) + "\n", encoding="utf-8")
    print(resumen)
    sys.exit(1 if resumen["FALHA"] else 0)


if __name__ == "__main__":
    main()
