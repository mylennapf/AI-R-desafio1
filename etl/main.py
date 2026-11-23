"""ETL completo da Verdejar: extracao -> transformacao -> carga.

Uso (na raiz do projeto, com a API e o banco no ar):
    python -m etl.main               extrai da API e grava brutos/
    python -m etl.main --sem-api     reprocessa a partir de brutos/, sem chamar a API
"""
import argparse
import sys

from etl.carga import ErroCarga, carregar, conectar
from etl.extracao import ErroExtracao, extrair_tudo
from etl.transformacao import ler_brutos, transformar_tudo


def main(argv=None):
    parser = argparse.ArgumentParser(description="ETL da Verdejar")
    parser.add_argument("--sem-api", action="store_true", help="usa os dados ja salvos em brutos/")
    args = parser.parse_args(argv)

    try:
        if args.sem_api:
            brutos = ler_brutos()
            clientes, pedidos, produtos = brutos["clientes"], brutos["pedidos"], brutos["produtos"]
            print("extracao: usando brutos/ (sem chamar a API)")
        else:
            clientes, pedidos, produtos = extrair_tudo()

        tabelas = transformar_tudo(clientes, pedidos, produtos)

        with conectar() as conexao:
            carregar(tabelas, conexao)
    except FileNotFoundError as erro:
        print(f"erro: dados brutos nao encontrados ({erro.filename}); rode sem --sem-api primeiro")
        return 1
    except (ErroExtracao, ErroCarga) as erro:
        print(f"erro: {erro}")
        return 1
    except (ValueError, KeyError) as erro:
        print(f"erro: registro invalido na transformacao: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
