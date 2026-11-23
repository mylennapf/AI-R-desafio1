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
