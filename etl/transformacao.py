"""Transformacao: trata as armadilhas A1 a A6 e prepara os registros para a carga.

Uso: python -m etl.transformacao   (le os dados de brutos/, sem chamar a API)

Cada funcao de tratamento e pura: recebe um valor ou registro e devolve um novo,
sem alterar a entrada. Os contadores sao calculados em transformar_tudo,
comparando a entrada com a saida.
"""
import json
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

PASTA_BRUTOS = Path(__file__).resolve().parent.parent / "brutos"
CENTAVO = Decimal("0.01")
FORMATOS_DATA = ("%Y-%m-%d", "%d/%m/%Y")  # A3: AAAA-MM-DD e DD/MM/AAAA


# ---------- funcoes de valor ----------

def converter_data(texto):
    """A3: converte 'AAAA-MM-DD' ou 'DD/MM/AAAA' em date."""
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    raise ValueError(f"data em formato desconhecido: {texto!r}")


def converter_valor(valor):
    """A4: converte numero ou texto com virgula decimal ('125,84') em Decimal com 2 casas."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError(f"valor monetario invalido: {valor!r}")
    if isinstance(valor, str):
        texto = valor.strip()
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")  # '1.234,56' -> '1234.56'
    else:
        texto = str(valor)  # str() evita o ruido binario do float: 94.34 -> '94.34'
    try:
        return Decimal(texto).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError(f"valor monetario invalido: {valor!r}") from None


def tratar_email(email):
    """A1: e-mail ausente ou em branco vira None; o cliente e mantido."""
    if email is None or not str(email).strip():
        return None
    return str(email).strip()


def padronizar_estado(estado):
    """A2: sigla do estado sempre em maiusculas, com 2 letras."""
    sigla = str(estado).strip().upper()
    if len(sigla) != 2 or not sigla.isalpha():
        raise ValueError(f"sigla de estado invalida: {estado!r}")
    return sigla


# ---------- funcoes de registro ----------

def transformar_cliente(cliente):
    return {
        "id": int(cliente["id"]),
        "nome": cliente["nome"].strip(),
        "email": tratar_email(cliente.get("email")),
        "cidade": cliente["cidade"].strip(),
        "estado": padronizar_estado(cliente["estado"]),
        "cadastro_em": converter_data(cliente["cadastro_em"]),
    }


def transformar_produto(produto):
    return {
        "produto_id": int(produto["produto_id"]),
        "nome": produto["nome"].strip(),
        "categoria": produto["categoria"].strip(),
        "preco_base": converter_valor(produto["preco_base"]),
    }


def remover_repetidos(pedidos):
    """A5: mantem a primeira ocorrencia de cada id. Devolve (unicos, descartados)."""
    vistos = set()
    unicos = []
    for pedido in pedidos:
        if pedido["id"] in vistos:
            continue
        vistos.add(pedido["id"])
        unicos.append(pedido)
    return unicos, len(pedidos) - len(unicos)


def transformar_itens(pedido_id, itens):
    """Numera as linhas de 1 a N, na ordem em que vieram da API."""
    return [
        {
            "pedido_id": pedido_id,
            "linha": linha,
            "produto_id": int(item["produto_id"]),
            "quantidade": int(item["quantidade"]),
            "preco_unitario": converter_valor(item["preco_unitario"]),
        }
        for linha, item in enumerate(itens, start=1)
    ]


def calcular_valor_itens(itens):
    """A6: soma de quantidade x preco_unitario dos itens ja transformados."""
    total = sum((i["quantidade"] * i["preco_unitario"] for i in itens), Decimal("0"))
    return total.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def is_divergente(valor_total, valor_itens):
    """A6: divergente quando a diferenca passa de um centavo."""
    return abs(valor_total - valor_itens) > CENTAVO


def transformar_pedido(pedido):
    """Devolve (pedido_tratado, itens_tratados)."""
    pedido_id = int(pedido["id"])
    itens = transformar_itens(pedido_id, pedido["itens"])
    valor_total = converter_valor(pedido["valor_total"])
    valor_itens = calcular_valor_itens(itens)
    tratado = {
        "id": pedido_id,
        "cliente_id": int(pedido["cliente_id"]),
        "data_pedido": converter_data(pedido["data_pedido"]),
        "status": pedido["status"].strip(),
        "valor_total": valor_total,
        "valor_itens": valor_itens,
        "divergente": is_divergente(valor_total, valor_itens),
    }
    return tratado, itens


# ---------- orquestracao ----------

def transformar_tudo(clientes_brutos, pedidos_brutos, produtos_brutos):
    """Aplica todas as transformacoes, imprime os contadores e devolve as tabelas."""
    clientes = [transformar_cliente(c) for c in clientes_brutos]
    produtos = [transformar_produto(p) for p in produtos_brutos]

    pedidos_unicos, repetidos = remover_repetidos(pedidos_brutos)
    pedidos, itens = [], []
    for bruto in pedidos_unicos:
        pedido, itens_pedido = transformar_pedido(bruto)
        pedidos.append(pedido)
        itens.extend(itens_pedido)

    contadores = {
        "pedidos_unicos": len(pedidos),
        "repetidos_descartados": repetidos,
        "emails_nulos": sum(c["email"] is None for c in clientes),
        "estados_padronizados": sum(
            b["estado"] != t["estado"] for b, t in zip(clientes_brutos, clientes)
        ),
        # datas que nao estavam em AAAA-MM-DD e precisaram de conversao de formato
        "datas_convertidas": sum(
            b["data_pedido"].strip() != t["data_pedido"].isoformat()
            for b, t in zip(pedidos_unicos, pedidos)
        ),
        # valores que vieram como texto e foram convertidos para numero
        "valores_convertidos": sum(isinstance(b["valor_total"], str) for b in pedidos_unicos),
        "divergentes": sum(p["divergente"] for p in pedidos),
    }

    print(f"transformacao: pedidos_unicos={contadores['pedidos_unicos']} "
          f"repetidos_descartados={contadores['repetidos_descartados']}")
    print(f"transformacao: emails_nulos={contadores['emails_nulos']} "
          f"estados_padronizados={contadores['estados_padronizados']} "
          f"datas_convertidas={contadores['datas_convertidas']} "
          f"valores_convertidos={contadores['valores_convertidos']}")
    print(f"transformacao: divergentes={contadores['divergentes']}")

    return {
        "clientes": clientes,
        "produtos": produtos,
        "pedidos": pedidos,
        "itens_pedido": itens,
        "contadores": contadores,
    }


def ler_brutos(pasta=PASTA_BRUTOS):
    dados = {}
    for nome in ("clientes", "pedidos", "produtos"):
        with open(pasta / f"{nome}.json", encoding="utf-8") as arquivo:
            dados[nome] = json.load(arquivo)
    return dados


def main():
    try:
        brutos = ler_brutos()
    except FileNotFoundError as erro:
        print(f"erro: dados brutos nao encontrados ({erro.filename}); rode antes: python -m etl.extracao")
        return 1
    try:
        transformar_tudo(brutos["clientes"], brutos["pedidos"], brutos["produtos"])
    except (ValueError, KeyError) as erro:
        print(f"erro: registro invalido na transformacao: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
