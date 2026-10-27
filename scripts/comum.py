"""Funções compartilhadas pelos scripts da Etapa 1 (configuração, downloads, manifesto, banco)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

import requests
import yaml

RAIZ = Path(__file__).resolve().parents[1]
MANIFESTO = RAIZ / "data" / "manifesto_fontes.json"
USER_AGENT = "sevilla-oferta-bus/0.1 (projeto de portfolio; uso nao comercial)"

# Saída UTF-8 no console do Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def carregar_config() -> dict:
    with open(RAIZ / "config" / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def caminho(rel: str) -> Path:
    return RAIZ / rel


def agora_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def hash_arquivo(path: Path, algoritmo: str = "sha256") -> str:
    h = hashlib.new(algoritmo)
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def sessao() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def baixar(url: str, destino: Path, md5_esperado: str | None = None, forcar: bool = False) -> dict:
    """Baixa `url` para `destino`, evitando novo download de arquivo idêntico.

    Critério para pular: arquivo local existente com md5 igual ao esperado ou, sem md5 esperado,
    tamanho igual ao Content-Length informado pelo servidor.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    s = sessao()
    cab = None
    for tentativa in range(3):
        try:
            cab = s.head(url, allow_redirects=True, timeout=60)
            break
        except requests.RequestException as erro:
            print(f"  aviso: HEAD {url} falhou ({type(erro).__name__}), tentativa {tentativa + 1}/3")
    if cab is None:
        if destino.exists() and not forcar:
            print(f"  servidor indisponível; mantida a cópia local {destino.name}")
            return {"url": url, "acao": "mantido (servidor indisponivel)",
                    "arquivo": str(destino.relative_to(RAIZ)).replace("\\", "/"),
                    "tamanho_bytes": destino.stat().st_size, "md5": hash_arquivo(destino, "md5"),
                    "sha256": hash_arquivo(destino)}
        raise RuntimeError(f"Não foi possível acessar {url}")
    info = {
        "url": url,
        "http_status_head": cab.status_code,
        "last_modified": cab.headers.get("Last-Modified"),
        "content_length": int(cab.headers["Content-Length"]) if "Content-Length" in cab.headers else None,
        "etag": cab.headers.get("ETag"),
    }
    if destino.exists() and not forcar:
        rel = str(destino.relative_to(RAIZ)).replace("\\", "/")
        anterior = {}
        if MANIFESTO.exists():
            anterior = next((v for v in json.loads(MANIFESTO.read_text(encoding="utf-8")).values()
                             if v.get("arquivo") == rel), {})
        if md5_esperado and hash_arquivo(destino, "md5") == md5_esperado:
            info["acao"] = "mantido (md5 identico)"
        elif not md5_esperado and info["content_length"] == destino.stat().st_size:
            info["acao"] = "mantido (tamanho identico)"
        elif (info["content_length"] is None and info["last_modified"]
              and info["last_modified"] == anterior.get("last_modified")
              and anterior.get("sha256") == hash_arquivo(destino)):
            info["acao"] = "mantido (Last-Modified e hash identicos)"
    if "acao" not in info:
        with s.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            tmp = destino.with_suffix(destino.suffix + ".part")
            with open(tmp, "wb") as f:
                for bloco in r.iter_content(1 << 20):
                    f.write(bloco)
            tmp.replace(destino)
        info["acao"] = "baixado"
        info["data_obtencao"] = agora_utc()
    md5 = hash_arquivo(destino, "md5")
    if md5_esperado and md5 != md5_esperado:
        raise RuntimeError(f"md5 divergente para {destino.name}: {md5} != {md5_esperado}")
    info.update(arquivo=str(destino.relative_to(RAIZ)).replace("\\", "/"),
                tamanho_bytes=destino.stat().st_size, md5=md5, sha256=hash_arquivo(destino))
    return info


def registrar_fonte(fonte_id: str, dados: dict) -> None:
    """Atualiza (ou cria) a entrada `fonte_id` no manifesto de fontes, preservando a data de obtenção."""
    manifesto = json.loads(MANIFESTO.read_text(encoding="utf-8")) if MANIFESTO.exists() else {}
    anterior = manifesto.get(fonte_id, {})
    novo = {**anterior, **dados}
    if "data_obtencao" not in dados and "data_obtencao" in anterior:
        novo["data_obtencao"] = anterior["data_obtencao"]
    novo.setdefault("data_obtencao", agora_utc())
    novo["ultima_verificacao"] = agora_utc()
    manifesto[fonte_id] = novo
    MANIFESTO.parent.mkdir(parents=True, exist_ok=True)
    MANIFESTO.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")


def conninfo(cfg: dict) -> str:
    """Parâmetros de conexão sem senha (a senha vem de PGPASSWORD ou do arquivo pgpass)."""
    b = cfg["banco"]
    return (f"host={os.environ.get('PGHOST', b['host'])} port={os.environ.get('PGPORT', b['port'])} "
            f"dbname={os.environ.get('PGDATABASE', b['dbname'])} user={os.environ.get('PGUSER', b['user'])}")


def conectar(cfg: dict):
    import psycopg
    return psycopg.connect(conninfo(cfg), connect_timeout=10)
