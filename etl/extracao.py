"""Extracao: API local da Verdejar (clientes e pedidos) e catalogo de produtos (CSV).

Uso: python -m etl.extracao
Grava os dados brutos em brutos/ antes de qualquer transformacao.
"""
import csv
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

URL_BASE = os.environ.get("VERDEJAR_API_URL", "http://127.0.0.1:8000")
PAGE_SIZE = 100  # a API aceita de 1 a 200
TIMEOUT_SEGUNDOS = 10

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_PRODUTOS = RAIZ / "insumos" / "dados" / "produtos.csv"
PASTA_BRUTOS = RAIZ / "brutos"


class ErroExtracao(Exception):
    """Falha de extracao com mensagem pronta para o usuario."""


def buscar_pagina(url_base, rota, page, page_size=PAGE_SIZE):
    """Busca uma pagina de uma rota e devolve o JSON como dicionario."""
    url = f"{url_base}/{rota}?{urlencode({'page': page, 'page_size': page_size})}"
    try:
        with urlopen(url, timeout=TIMEOUT_SEGUNDOS) as resposta:
            if resposta.status != 200:
                raise ErroExtracao(f"rota /{rota} pagina {page}: status HTTP {resposta.status} inesperado")
            corpo = resposta.read().decode("utf-8")
    except HTTPError as erro:
        if erro.code == 404:
            raise ErroExtracao(f"rota /{rota} pagina {page}: pagina inexistente (HTTP 404)") from None
        raise ErroExtracao(f"rota /{rota} pagina {page}: status HTTP {erro.code}") from None
    except URLError as erro:
        raise ErroExtracao(
            f"nao foi possivel conectar em {url_base} ({erro.reason}); a API esta rodando?"
        ) from None
    except TimeoutError:
        raise ErroExtracao(f"rota /{rota} pagina {page}: sem resposta em {TIMEOUT_SEGUNDOS}s") from None

    try:
        return json.loads(corpo)
    except json.JSONDecodeError:
        raise ErroExtracao(f"rota /{rota} pagina {page}: resposta nao e JSON valido") from None


def extrair_rota(url_base, rota, page_size=PAGE_SIZE):
    """Percorre todas as paginas da rota ate total_pages.

    Devolve (registros, paginas_lidas).
    """
    primeira = buscar_pagina(url_base, rota, 1, page_size)
    total_paginas = primeira["total_pages"]
    registros = list(primeira["items"])
    for page in range(2, total_paginas + 1):
        registros.extend(buscar_pagina(url_base, rota, page, page_size)["items"])

    if len(registros) != primeira["total_items"]:
        raise ErroExtracao(
            f"rota /{rota}: esperava {primeira['total_items']} registros, recebeu {len(registros)}"
        )
    return registros, total_paginas


def ler_produtos(caminho=CAMINHO_PRODUTOS):
    """Le o catalogo de produtos. Os valores ficam como texto (brutos)."""
    try:
        with open(caminho, encoding="utf-8", newline="") as arquivo:
            return list(csv.DictReader(arquivo))
    except FileNotFoundError:
        raise ErroExtracao(f"arquivo de produtos nao encontrado: {caminho}") from None


def salvar_brutos(nome, dados, pasta=PASTA_BRUTOS):
    pasta.mkdir(exist_ok=True)
    caminho = pasta / f"{nome}.json"
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=1)
    return caminho


def extrair_tudo(url_base=URL_BASE):
    """Extrai as tres fontes, grava os brutos e imprime os contadores."""
    clientes, paginas_clientes = extrair_rota(url_base, "clientes")
    pedidos, paginas_pedidos = extrair_rota(url_base, "pedidos")
    produtos = ler_produtos()

    salvar_brutos("clientes", clientes)
    salvar_brutos("pedidos", pedidos)
    salvar_brutos("produtos", produtos)

    print(f"extracao: clientes paginas={paginas_clientes} registros={len(clientes)}")
    print(f"extracao: pedidos paginas={paginas_pedidos} registros_brutos={len(pedidos)}")
    print(f"extracao: produtos registros={len(produtos)}")
    return clientes, pedidos, produtos


def main():
    try:
        extrair_tudo()
    except ErroExtracao as erro:
        print(f"erro: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
