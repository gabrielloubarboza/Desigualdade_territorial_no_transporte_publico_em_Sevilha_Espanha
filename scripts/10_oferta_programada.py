"""Etapa 3 — Linhas acessíveis e frequência programada (SQL 09–12).

Uso:  .venv\\Scripts\\python.exe scripts\\10_oferta_programada.py

Reutiliza prep.gtfs_horarios_dia (Etapa 1) e analise.origem_parada_400m (Etapa 2); não refaz a
interpolação nem o roteamento. Idempotente: recria apenas as tabelas da Etapa 3 no schema `analise`.
"""
from __future__ import annotations

import time

from comum import caminho, carregar_config, conectar

CFG = carregar_config()
ARQUIVOS = ["09_oferta_partidas.sql", "10_oferta_origem.sql", "11_oferta_agregacao.sql", "12_oferta_sensibilidade.sql"]


def executar(conn):
    for arq in ARQUIVOS:
        t = time.time()
        conn.execute(caminho(f"sql/{arq}").read_text(encoding="utf-8"))
        conn.commit()
        print(f"  sql/{arq} ({time.time() - t:.0f} s)")


def main():
    t0 = time.time()
    with conectar(CFG) as conn:
        executar(conn)
        for r in conn.execute("""
                SELECT periodo, viagens_rede, linhas_rede, round(media_linhas::numeric, 2),
                       round(media_partidas_hora::numeric, 1), round(pct_sem_oferta_acessivel::numeric, 2)
                FROM analise.sintese_oferta_municipal ORDER BY inicio""").fetchall():
            print("  {}: {} viagens na rede, {} linhas; média {} linhas e {} partidas/h acessíveis; "
                  "{}% sem oferta acessível".format(*r))
    print(f"Concluído em {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
