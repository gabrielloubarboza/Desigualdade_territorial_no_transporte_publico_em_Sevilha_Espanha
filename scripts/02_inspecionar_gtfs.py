"""Etapa 1 — Inspeção estrutural e temporal do GTFS TUSSAM.

Uso:  .venv\\Scripts\\python.exe scripts\\02_inspecionar_gtfs.py

Gera data/processed/gtfs_inspecao.json (resumido em docs/gtfs_tussam.md). Não calcula frequências por
parada nem indicadores territoriais: apenas verifica se o feed permite calculá-los.
"""
from __future__ import annotations

import datetime as dt
import json

import geopandas as gpd
import numpy as np
import pandas as pd

from comum import carregar_config, caminho

CFG = carregar_config()
DIR = caminho("data/raw/gtfs_tussam/extract")
ESPERADOS = ["agency", "stops", "routes", "trips", "stop_times", "calendar", "calendar_dates",
             "frequencies", "shapes", "feed_info"]
# Feriados nacionais/autonômicos (Andalucía) dentro da vigência do feed — usados só para escolher o
# dia de referência. Fonte: Decreto da Junta de Andalucía para o calendário laboral 2026 e BOE 2027.
FERIADOS = {"2026-10-12": "Fiesta Nacional", "2026-11-02": "Todos los Santos (trasladado)",
            "2026-12-07": "Día de la Constitución (trasladado)", "2026-12-08": "Inmaculada Concepción",
            "2026-12-25": "Natividad", "2027-01-01": "Año Nuevo", "2027-01-06": "Epifanía"}
DIAS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def seg(h: str) -> int:
    a, b, c = map(int, h.split(":"))
    return a * 3600 + b * 60 + c


def ler(nome: str) -> pd.DataFrame | None:
    p = DIR / f"{nome}.txt"
    if not p.exists():
        return None
    return pd.read_csv(p, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8-sig")


def main():
    t = {n: ler(n) for n in ESPERADOS}
    res: dict = {"arquivos": {n: (None if df is None else len(df)) for n, df in t.items()}}
    ag, ro, tr, st, sp, ca = (t[k] for k in ("agency", "routes", "trips", "stop_times", "stops", "calendar"))
    cd, fi = t["calendar_dates"], t["feed_info"]

    res["agency"] = ag.to_dict("records")
    res["feed_info"] = fi.to_dict("records") if fi is not None else None
    res["timezone_ok"] = bool((ag.agency_timezone == "Europe/Madrid").all())

    # Modos
    modos = ro.groupby("route_type").route_short_name.apply(list).to_dict()
    res["route_types"] = {k: {"n_rotas": len(v), "linhas": v} for k, v in modos.items()}
    viagens_por_tipo = tr.merge(ro[["route_id", "route_type"]], on="route_id").route_type.value_counts().to_dict()
    res["viagens_por_route_type"] = viagens_por_tipo

    # Calendário
    res["calendar"] = ca.to_dict("records")
    res["calendar_dates_registros"] = 0 if cd is None else len(cd)
    res["viagens_por_service"] = tr.service_id.value_counts().to_dict()

    # Paradas
    lat, lon = sp.stop_lat.astype(float), sp.stop_lon.astype(float)
    res["paradas"] = {
        "n": len(sp), "ids_unicos": bool(sp.stop_id.is_unique),
        "lat_min_max": [lat.min(), lat.max()], "lon_min_max": [lon.min(), lon.max()],
        "sem_coordenada": int((lat.isna() | lon.isna()).sum()),
        "location_type_valores": sp.location_type.fillna("(vazio)").value_counts().to_dict(),
        "com_parent_station": int(sp.parent_station.notna().sum()),
        "sem_uso_em_stop_times": int((~sp.stop_id.isin(st.stop_id)).sum()),
    }

    # Integridade referencial
    res["integridade"] = {
        "trips_route_inexistente": int((~tr.route_id.isin(ro.route_id)).sum()),
        "trips_service_inexistente": int((~tr.service_id.isin(ca.service_id)).sum()),
        "stop_times_trip_inexistente": int((~st.trip_id.isin(tr.trip_id)).sum()),
        "stop_times_stop_inexistente": int((~st.stop_id.isin(sp.stop_id)).sum()),
        "trips_sem_stop_times": int((~tr.trip_id.isin(st.trip_id)).sum()),
        "trip_id_duplicado": int(tr.trip_id.duplicated().sum()),
        "trip_seq_duplicado": int(st.duplicated(["trip_id", "stop_sequence"]).sum()),
        "shape_id_preenchido": int(tr.shape_id.notna().sum()),
    }

    # Estrutura temporal
    st["seq"] = st.stop_sequence.astype(int)
    st = st.sort_values(["trip_id", "seq"]).reset_index(drop=True)
    st["tem_hora"] = st.departure_time.notna()
    g = st.groupby("trip_id", sort=False)
    prim, ult = g.head(1), g.tail(1)
    horas = st.departure_time.dropna()
    tp = st[st.tem_hora].copy()
    tp["s"] = tp.departure_time.map(seg)
    tp["dt"] = tp.groupby("trip_id").s.diff()
    tp["dd"] = tp.groupby("trip_id").seq.diff()
    vel = (tp.dd / tp.dt * 3.6).dropna()
    st["bloco"] = g.tem_hora.cumsum()
    corridas = st[~st.tem_hora].groupby(["trip_id", "bloco"]).size()
    res["tempo"] = {
        "stop_times_total": len(st),
        "com_horario_explicito": int(st.tem_hora.sum()),
        "sem_horario": int((~st.tem_hora).sum()),
        "pct_explicito": round(100 * st.tem_hora.mean(), 2),
        "coluna_timepoint_presente": "timepoint" in st.columns,
        "arrival_diferente_departure": int((st.arrival_time.fillna("") != st.departure_time.fillna("")).sum()),
        "primeira_parada_sem_hora": int((~prim.tem_hora).sum()),
        "ultima_parada_sem_hora": int((~ult.tem_hora).sum()),
        "viagens_sem_nenhuma_hora": int((g.tem_hora.sum() == 0).sum()),
        "horario_min": horas.min(), "horario_max": horas.max(),
        "registros_apos_24h": int((horas >= "24:00:00").sum()),
        "intervalo_entre_pontos_controle_min": (tp.dt.dropna() / 60).describe().round(2).to_dict(),
        "paradas_sem_hora_consecutivas": corridas.describe().round(2).to_dict(),
        "diferenca_tempo_negativa_ou_zero": int((tp.dt <= 0).sum()),
        "paradas_por_viagem": g.size().describe().round(2).to_dict(),
        "viagens_inicio_seq_maior_que_zero": int((prim.seq > 0).sum()),
    }

    # stop_sequence como distância acumulada (m): razão com distância euclidiana entre paradas consecutivas
    gp = gpd.GeoDataFrame(sp, geometry=gpd.points_from_xy(lon, lat), crs=4326).to_crs(CFG["projeto"]["crs_metrico"])
    xy = pd.DataFrame({"stop_id": gp.stop_id, "x": gp.geometry.x, "y": gp.geometry.y})
    s2 = st[["trip_id", "stop_id", "seq"]].merge(xy, on="stop_id", how="left")
    gg = s2.groupby("trip_id", sort=False)
    de = np.hypot(gg.x.diff(), gg.y.diff())
    dseq = gg.seq.diff()
    ok = de > 0
    razao = dseq[ok] / de[ok]
    res["stop_sequence_como_distancia"] = {
        "razao_dseq_euclid": razao.describe(percentiles=[.01, .05, .5, .95, .99]).round(3).to_dict(),
        "pct_razao_menor_0_95": round(100 * (razao < 0.95).mean(), 3),
        "velocidade_kmh_entre_pontos_controle": vel.describe(percentiles=[.01, .5, .99]).round(2).to_dict(),
        "trechos_velocidade_acima_60kmh": int((vel > 60).sum()),
    }

    # Dia de referência
    dia = dt.date.fromisoformat(CFG["gtfs"]["dia_referencia"])
    ds = dia.strftime("%Y%m%d")
    fi0 = fi.iloc[0]
    ativos = ca[(ca[DIAS[dia.weekday()]] == "1") & (ca.start_date <= ds) & (ca.end_date >= ds)].service_id.tolist()
    if cd is not None and len(cd):
        ativos = sorted(set(ativos) - set(cd[(cd.date == ds) & (cd.exception_type == "2")].service_id)
                        | set(cd[(cd.date == ds) & (cd.exception_type == "1")].service_id))
    tr_dia = tr[tr.service_id.isin(ativos)].merge(ro[["route_id", "route_short_name", "route_type"]], on="route_id")
    bus = tr_dia[tr_dia.route_type == "3"]
    res["dia_referencia"] = {
        "data": dia.isoformat(), "dia_semana": DIAS[dia.weekday()],
        "dentro_feed_info": fi0.feed_start_date <= ds <= fi0.feed_end_date,
        "feriado_conhecido": FERIADOS.get(dia.isoformat()),
        "feriados_na_vigencia_nao_codificados": FERIADOS,
        "servicos_ativos": ativos,
        "viagens_total": len(tr_dia), "viagens_onibus": len(bus),
        "viagens_bonde": int((tr_dia.route_type == "0").sum()),
        "linhas_onibus_com_servico": int(bus.route_id.nunique()),
        "linhas_onibus_sem_servico": sorted(set(ro[ro.route_type == "3"].route_short_name)
                                            - set(bus.route_short_name)),
    }
    # Viagens de ônibus em operação em cada período (informativo, não é indicador por parada)
    ini = st[st.tem_hora].groupby("trip_id").departure_time.agg(["min", "max"])
    b = bus.merge(ini, left_on="trip_id", right_index=True)
    per = {}
    for nome, (h0, h1) in CFG["gtfs"]["periodos"].items():
        per[nome] = {"intervalo": f"{h0}-{h1}",
                     "viagens_onibus_iniciadas": int(((b["min"] >= h0) & (b["min"] < h1)).sum()),
                     "viagens_onibus_em_curso": int(((b["min"] < h1) & (b["max"] >= h0)).sum())}
    res["periodos_preparados"] = per

    saida = caminho("data/processed/gtfs_inspecao.json")
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("arquivos", "tempo", "dia_referencia", "periodos_preparados")},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
