"""Testes das funcoes de transformacao: uma entrada conhecida e a saida esperada por armadilha."""
from datetime import date
from decimal import Decimal

import pytest

from etl.transformacao import (
    calcular_valor_itens,
    converter_data,
    converter_valor,
    is_divergente,
    padronizar_estado,
    remover_repetidos,
    transformar_cliente,
    transformar_pedido,
)


# ---------- A1: e-mail ausente ----------

def test_a1_cliente_sem_email_e_mantido_com_email_nulo():
    bruto = {"id": 7, "nome": "Ana", "email": None, "cidade": "Pelotas", "estado": "RS",
             "cadastro_em": "2025-01-10"}
    cliente = transformar_cliente(bruto)
    assert cliente["id"] == 7
    assert cliente["email"] is None


def test_a1_email_em_branco_vira_nulo():
    assert transformar_cliente({"id": 1, "nome": "B", "email": "  ", "cidade": "X", "estado": "SP",
                                "cadastro_em": "2025-01-10"})["email"] is None


# ---------- A2: estado em caixa mista ----------

def test_a2_estado_minusculo_vira_maiusculo():
    assert padronizar_estado("rs") == "RS"
    assert padronizar_estado("SC") == "SC"


def test_a2_estado_invalido_gera_erro():
    with pytest.raises(ValueError):
        padronizar_estado("R")


# ---------- A3: data em dois formatos (obrigatorio) ----------

def test_a3_data_iso_e_brasileira_viram_a_mesma_data():
    assert converter_data("2026-02-19") == date(2026, 2, 19)
    assert converter_data("19/02/2026") == date(2026, 2, 19)


def test_a3_data_em_formato_desconhecido_gera_erro():
    with pytest.raises(ValueError):
        converter_data("02-19-2026")


# ---------- A4: valor com virgula decimal (obrigatorio) ----------

def test_a4_valor_com_virgula_vira_numero():
    assert converter_valor("125,84") == Decimal("125.84")


def test_a4_valor_numerico_permanece_com_duas_casas():
    assert converter_valor(94.34) == Decimal("94.34")
    assert converter_valor(3.5) == Decimal("3.50")


def test_a4_valor_invalido_gera_erro():
    with pytest.raises(ValueError):
        converter_valor("abc")


# ---------- A5: pedido repetido (obrigatorio) ----------

def test_a5_pedido_repetido_fica_uma_vez_mantendo_a_primeira_ocorrencia():
    pedidos = [
        {"id": 1, "origem": "pagina 1"},
        {"id": 2, "origem": "pagina 1"},
        {"id": 1, "origem": "pagina 3"},
    ]
    unicos, descartados = remover_repetidos(pedidos)
    assert [p["id"] for p in unicos] == [1, 2]
    assert unicos[0]["origem"] == "pagina 1"
    assert descartados == 1


def test_a5_aplicar_duas_vezes_nao_muda_o_resultado():
    pedidos = [{"id": 1}, {"id": 1}, {"id": 2}]
    unicos, _ = remover_repetidos(pedidos)
    de_novo, descartados = remover_repetidos(unicos)
    assert de_novo == unicos
    assert descartados == 0


# ---------- A6: valor_total diferente da soma dos itens ----------

def test_a6_valor_itens_e_soma_de_quantidade_vezes_preco():
    itens = [
        {"quantidade": 3, "preco_unitario": Decimal("4.30")},
        {"quantidade": 5, "preco_unitario": Decimal("15.86")},
        {"quantidade": 4, "preco_unitario": Decimal("9.66")},
    ]
    assert calcular_valor_itens(itens) == Decimal("130.84")


def test_a6_tolerancia_de_um_centavo():
    assert not is_divergente(Decimal("10.00"), Decimal("10.01"))
    assert is_divergente(Decimal("10.00"), Decimal("10.02"))


def test_a6_pedido_divergente_grava_os_dois_valores_e_marca():
    # Pedido 1 real da API: valor_total "125,84", mas os itens somam 130.84.
    bruto = {"id": 1, "cliente_id": 303, "data_pedido": "2026-02-19", "status": "entregue",
             "valor_total": "125,84",
             "itens": [{"produto_id": 2, "quantidade": 3, "preco_unitario": 4.3},
                       {"produto_id": 9, "quantidade": 5, "preco_unitario": 15.86},
                       {"produto_id": 7, "quantidade": 4, "preco_unitario": 9.66}]}
    pedido, itens = transformar_pedido(bruto)
    assert pedido["valor_total"] == Decimal("125.84")
    assert pedido["valor_itens"] == Decimal("130.84")
    assert pedido["divergente"] is True
    assert [i["linha"] for i in itens] == [1, 2, 3]
