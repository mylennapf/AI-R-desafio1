"""Carga: grava as tabelas transformadas no PostgreSQL (caminho B, Docker).

A conexao usa as variaveis PGHOST, PGPORT, PGDATABASE, PGUSER e PGPASSWORD,
lidas do ambiente ou do arquivo .env na raiz do projeto (fora do Git).

Idempotencia: recarga completa em uma unica transacao. As quatro tabelas sao
esvaziadas (TRUNCATE) e preenchidas de novo; se algo falhar no meio, o ROLLBACK
devolve o banco ao estado anterior. Rodar duas vezes deixa as mesmas contagens.
"""
import os
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent

# Ordem de insercao respeita as chaves estrangeiras: pais antes dos filhos.
ORDEM_CARGA = ("produtos", "clientes", "pedidos", "itens_pedido")

COLUNAS = {
    "produtos": ("produto_id", "nome", "categoria", "preco_base"),
    "clientes": ("id", "nome", "email", "cidade", "estado", "cadastro_em"),
    "pedidos": ("id", "cliente_id", "data_pedido", "status", "valor_total", "valor_itens", "divergente"),
    "itens_pedido": ("pedido_id", "linha", "produto_id", "quantidade", "preco_unitario"),
}


class ErroCarga(Exception):
    """Falha de conexao ou de carga com mensagem pronta para o usuario."""


def ler_env(caminho=RAIZ / ".env"):
    """Le pares CHAVE=valor do .env sem sobrescrever variaveis ja definidas no ambiente."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip())


def conectar():
    """Abre a conexao. A libpq le PGHOST, PGPORT, PGDATABASE, PGUSER e PGPASSWORD do ambiente."""
    ler_env()
    try:
        return psycopg.connect(connect_timeout=5)
    except psycopg.OperationalError as erro:
        # A mensagem da libpq nao inclui a senha.
        raise ErroCarga(
            f"nao foi possivel conectar ao PostgreSQL em "
            f"{os.environ.get('PGHOST')}:{os.environ.get('PGPORT')} ({str(erro).strip()}); "
            f"o conteiner verdejar-pg esta rodando?"
        ) from None


def montar_insert(tabela):
    """INSERT com placeholders %s: os dados nunca sao concatenados ao SQL."""
    colunas = COLUNAS[tabela]
    return f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({', '.join(['%s'] * len(colunas))})"


def contar_linhas(conexao):
    with conexao.cursor() as cursor:
        contagens = {}
        for tabela in ORDEM_CARGA:
            cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
            contagens[tabela] = cursor.fetchone()[0]
    return contagens


def carregar(tabelas, conexao):
    """Recarga completa e atomica. Devolve as contagens lidas do banco depois do COMMIT."""
    try:
        with conexao.transaction():
            with conexao.cursor() as cursor:
                cursor.execute("TRUNCATE itens_pedido, pedidos, clientes, produtos")
                for tabela in ORDEM_CARGA:
                    colunas = COLUNAS[tabela]
                    linhas = [tuple(registro[c] for c in colunas) for registro in tabelas[tabela]]
                    cursor.executemany(montar_insert(tabela), linhas)
    except psycopg.Error as erro:
        raise ErroCarga(f"carga desfeita (rollback): {str(erro).strip()}") from None

    contagens = contar_linhas(conexao)
    print(
        f"carga: clientes={contagens['clientes']} produtos={contagens['produtos']} "
        f"pedidos={contagens['pedidos']} itens={contagens['itens_pedido']}"
    )
    return contagens
