"""Reconciliacao e teste de consulta: precisam do banco no ar e dos dados em brutos/.

O fixture executa a carga a partir de brutos/ antes dos testes, para que o
teste valha "apos a carga" mesmo rodando sozinho. Se o banco ou os brutos nao
estiverem disponiveis, os testes sao pulados (skip) com o motivo.
"""
import contextlib
import io

import pytest

from etl.carga import ErroCarga, carregar, conectar
from etl.reconciliacao import TOLERANCIA, resumo_destino, resumo_origem
from etl.transformacao import ler_brutos, transformar_tudo


@pytest.fixture(scope="module")
def carga():
    try:
        brutos = ler_brutos()
    except FileNotFoundError:
        pytest.skip("brutos/ nao encontrado; rode python -m etl.main antes")
    try:
        conexao = conectar()
    except ErroCarga as erro:
        pytest.skip(f"banco indisponivel: {erro}")
    with contextlib.redirect_stdout(io.StringIO()):
        tabelas = transformar_tudo(brutos["clientes"], brutos["pedidos"], brutos["produtos"])
        carregar(tabelas, conexao)
    yield brutos, conexao
    conexao.close()


def test_reconciliacao_contagem_de_pedidos(carga):
    brutos, conexao = carga
    assert resumo_destino(conexao)["pedidos"] == resumo_origem(brutos["pedidos"])["pedidos"]


def test_reconciliacao_soma_valor_itens_tolerando_um_centavo(carga):
    brutos, conexao = carga
    origem = resumo_origem(brutos["pedidos"])["soma_valor_itens"]
    destino = resumo_destino(conexao)["soma_valor_itens"]
    assert abs(origem - destino) <= TOLERANCIA


def test_consulta_vendas_por_mes_soma_igual_a_soma_geral(carga):
    """Teste de consulta (a): a soma dos meses bate com a soma geral da tabela pedidos."""
    _, conexao = carga
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT SUM(total_itens), SUM(total_informado) FROM ("
            "  SELECT DATE_TRUNC('month', data_pedido) AS mes,"
            "         SUM(valor_itens) AS total_itens, SUM(valor_total) AS total_informado"
            "  FROM pedidos GROUP BY 1) AS por_mes"
        )
        soma_meses_itens, soma_meses_informado = cursor.fetchone()
        cursor.execute("SELECT SUM(valor_itens), SUM(valor_total) FROM pedidos")
        soma_geral_itens, soma_geral_informado = cursor.fetchone()
    assert soma_meses_itens == soma_geral_itens
    assert soma_meses_informado == soma_geral_informado
