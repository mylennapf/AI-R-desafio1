"""Reconciliacao: compara contagens e somas da origem (brutos) com o destino (banco).

A origem e recalculada direto dos dados brutos, sem usar as funcoes de
transformacao, para que um erro nelas nao se esconda dos dois lados da conta.
"""
from decimal import Decimal

TOLERANCIA = Decimal("0.01")


def resumo_origem(pedidos_brutos):
    """Pedidos unicos (primeira ocorrencia) e soma de quantidade x preco_unitario."""
    vistos = set()
    soma = Decimal("0")
    for pedido in pedidos_brutos:
        if pedido["id"] in vistos:
            continue
        vistos.add(pedido["id"])
        for item in pedido["itens"]:
            soma += item["quantidade"] * Decimal(str(item["preco_unitario"]))
    return {"pedidos": len(vistos), "soma_valor_itens": soma}


def resumo_destino(conexao):
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(valor_itens), 0), COUNT(*) FILTER (WHERE divergente) FROM pedidos"
        )
        pedidos, soma, divergentes = cursor.fetchone()
    return {"pedidos": pedidos, "soma_valor_itens": soma, "divergentes": divergentes}


def reconciliar(pedidos_brutos, conexao):
    """Imprime a reconciliacao e devolve True quando origem e destino batem."""
    origem = resumo_origem(pedidos_brutos)
    destino = resumo_destino(conexao)
    diferenca = abs(origem["soma_valor_itens"] - destino["soma_valor_itens"])
    ok = origem["pedidos"] == destino["pedidos"] and diferenca <= TOLERANCIA

    print(f"reconciliacao: pedidos_origem={origem['pedidos']} pedidos_destino={destino['pedidos']}")
    print(f"reconciliacao: soma_valor_itens_origem={origem['soma_valor_itens']:.2f} "
          f"soma_valor_itens_destino={destino['soma_valor_itens']:.2f} diferenca={diferenca:.2f}")
    print(f"divergentes: {destino['divergentes']} pedidos com valor_total diferente da soma dos itens")
    if not ok:
        print("reconciliacao: FALHOU")
    return ok
