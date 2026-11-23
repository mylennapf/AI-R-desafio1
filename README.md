# Desafio Final do Bootcamp: ETL da Verdejar

ETL que extrai clientes e pedidos da API local da Verdejar e o catálogo de produtos do CSV, trata as armadilhas A1 a A6 e carrega tudo no PostgreSQL.

## Estrutura

```
README.md
COMO_USEI_IA.md
insumos/   gerar_dados.py, api_verdejar.py, schema.sql, schema_sqlite.sql, dados/
etl/       código do ETL
tests/     testes com pytest
brutos/    dados extraídos da API (fora do Git, ver .gitignore)
```

## Banco de dados: caminho B (PostgreSQL 16 em Docker)

O Docker já estava instalado nesta máquina, então usei o caminho B. A porta do host é **5433**, porque a 5432 já estava ocupada por outro projeto local.

1. Copie `.env.example` para `.env` e defina uma senha em `PGPASSWORD`. O `.env` não é versionado.
2. Suba o contêiner (PowerShell, uma linha):

   ```
   docker run --name verdejar-pg -e POSTGRES_PASSWORD=<sua_senha> -e POSTGRES_DB=verdejar -p 5433:5432 -d postgres:16
   ```

3. Aplique o esquema (PowerShell, uma linha):

   ```
   Get-Content insumos\schema.sql | docker exec -i verdejar-pg psql -U postgres -d verdejar
   ```

   No bash, o equivalente é `docker exec -i verdejar-pg psql -U postgres -d verdejar < insumos/schema.sql`.

Biblioteca de conexão: `psycopg` (versão 3). Instalação: `python -m pip install -r requirements.txt`.

## API local

```
cd insumos
python api_verdejar.py
```

Em outro terminal: `curl http://127.0.0.1:8000/saude` deve responder `{"status": "ok"}`.

## Extração (Parte 1)

Com a API rodando, na raiz do repositório:

```
python -m etl.extracao
```

O código está em `etl/extracao.py` e usa apenas a biblioteca padrão (`urllib`, `csv`, `json`):

- `buscar_pagina` pede uma página com `page` e `page_size=100` e confere se o status HTTP é 200. Página inexistente (404), outros status, falha de conexão, timeout e JSON inválido viram uma `ErroExtracao` com mensagem clara.
- `extrair_rota` percorre as páginas de 1 até `total_pages` e confere se a quantidade recebida bate com `total_items`.
- `ler_produtos` lê o `produtos.csv` com `csv.DictReader`.
- Os dados brutos são gravados em `brutos/clientes.json`, `brutos/pedidos.json` e `brutos/produtos.json` antes de qualquer transformação.
- Em caso de erro, o programa imprime `erro: ...` e termina com código 1, sem traceback.
- A URL da API pode ser trocada pela variável de ambiente `VERDEJAR_API_URL`.

Saída da extração:

```
extracao: clientes paginas=10 registros=1000
extracao: pedidos paginas=51 registros_brutos=5100
extracao: produtos registros=12
```

Saída com a API fora do ar (`VERDEJAR_API_URL=http://127.0.0.1:8999`):

```
erro: nao foi possivel conectar em http://127.0.0.1:8999 ([WinError 10061] Nenhuma conexão pôde ser feita porque a máquina de destino as recusou ativamente); a API esta rodando?
```

Saída ao pedir uma página inexistente (`buscar_pagina(URL_BASE, "pedidos", 999)`):

```
erro: rota /pedidos pagina 999: pagina inexistente (HTTP 404)
```

## Transformação e contrato de dados (Parte 2)

A transformação lê os arquivos de `brutos/`, sem chamar a API de novo:

```
python -m etl.transformacao
```

As regras de cada campo estão em [`CONTRATO_DE_DADOS.md`](CONTRATO_DE_DADOS.md). Cada armadilha é tratada por uma função pequena e pura em `etl/transformacao.py`:

| Armadilha | Função |
|---|---|
| A1 e-mail ausente | `tratar_email` |
| A2 estado em minúsculas | `padronizar_estado` |
| A3 data em dois formatos | `converter_data` |
| A4 valor com vírgula | `converter_valor` |
| A5 pedido repetido | `remover_repetidos` |
| A6 total diferente dos itens | `calcular_valor_itens` e `is_divergente` |

Saída:

```
transformacao: pedidos_unicos=5000 repetidos_descartados=100
transformacao: emails_nulos=81 estados_padronizados=151 datas_convertidas=1037 valores_convertidos=1255
transformacao: divergentes=238
```

Os números foram conferidos assim:
- 5100 pedidos brutos menos 100 repetidos dá 5000 pedidos únicos. As cópias repetidas têm o conteúdo idêntico ao da primeira ocorrência.
- As datas convertidas (1037) e os valores convertidos (1255) contam só os pedidos únicos. Nos brutos, que incluem as cópias, são 1054 e 1287.
- Os 238 pedidos divergentes têm diferença de pelo menos R$ 3,00. Nos outros 4762 a diferença é zero, então a tolerância de 1 centavo não deixa casos ambíguos.
- Total de itens: 12455. Soma de `valor_itens`: 311228.75.
