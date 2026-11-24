# Desafio Final do Bootcamp: ETL da Verdejar

ETL que extrai clientes e pedidos da API local da Verdejar e o catálogo de produtos do CSV, trata as armadilhas A1 a A6 e carrega tudo no PostgreSQL.

**Uso de IA:** o registro de sugestões aceitas, sugestões rejeitadas e falhas com retrabalho está em [`COMO_USEI_IA.md`](COMO_USEI_IA.md).

## Como rodar do zero

Pré-requisitos: Python 3, Docker e Git. Todos os comandos rodam na raiz do repositório, no PowerShell.

1. Instale as dependências (psycopg e pytest):

   ```
   python -m pip install -r requirements.txt
   ```

2. Crie o `.env` a partir do exemplo e defina uma senha em `PGPASSWORD`:

   ```
   Copy-Item .env.example .env
   ```

3. Suba o PostgreSQL. Use a mesma senha do `.env`:

   ```
   docker run --name verdejar-pg -e POSTGRES_PASSWORD=<sua_senha> -e POSTGRES_DB=verdejar -p 5433:5432 -d postgres:16
   ```

4. Aplique o esquema:

   ```
   Get-Content insumos\schema.sql | docker exec -i verdejar-pg psql -U postgres -d verdejar
   ```

5. Em outro terminal, suba a API e deixe-a rodando:

   ```
   cd insumos
   python api_verdejar.py
   ```

6. Rode o ETL completo (extração, transformação, carga e reconciliação):

   ```
   python -m etl.main
   ```

7. Rode os testes:

   ```
   python -m pytest -v
   ```

8. (Opcional) Rode as consultas de validação:

   ```
   Get-Content consultas_validacao.sql | docker exec -i verdejar-pg psql -U postgres -d verdejar
   ```

Se o computador ou o Docker reiniciar, religue o banco com `docker start verdejar-pg`. Os dados continuam lá.

As seções a seguir detalham cada etapa e trazem as evidências de execução.

## Estrutura

```
README.md                 este arquivo: como rodar, decisões e evidências
COMO_USEI_IA.md           registro do uso da IA
CONTRATO_DE_DADOS.md      campos, tipos, nulos e regras de cada tabela de destino
consultas_validacao.sql   consultas (a) vendas por mês, (b) pedidos por estado, (c) divergentes
requirements.txt          dependências (psycopg, pytest)
pytest.ini                configuração do pytest
.env.example              modelo das variáveis de conexão (o .env real fica fora do Git)
insumos/                  gerar_dados.py, api_verdejar.py, schema.sql, schema_sqlite.sql, dados/
etl/
  extracao.py             API paginada e CSV, grava brutos/
  transformacao.py        armadilhas A1 a A6 em funções puras e contadores
  carga.py                conexão e recarga transacional no PostgreSQL
  reconciliacao.py        compara contagens e somas entre origem e destino
  main.py                 executa o ETL completo
tests/
  test_transformacao.py   testes das armadilhas A1 a A6
  test_reconciliacao.py   reconciliação e teste de consulta (precisa do banco)
brutos/                   dados extraídos da API (fora do Git, ver .gitignore)
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

## Carga no banco (Parte 3)

ETL completo, com a API e o contêiner no ar:

```
python -m etl.main            (extrai da API, transforma e carrega)
python -m etl.main --sem-api  (reprocessa a partir de brutos/, sem chamar a API)
```

O código está em `etl/carga.py`, com `psycopg` 3:

- **Conexão:** as variáveis `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` e `PGPASSWORD` vêm do ambiente ou do `.env`. A senha não aparece no código nem nas mensagens.
- **Ordem da carga:** produtos, clientes, pedidos e itens_pedido. Os pais entram antes dos filhos, para respeitar as chaves estrangeiras.
- **Consultas parametrizadas:** todo `INSERT` usa placeholders `%s` com `executemany`. Os dados nunca são concatenados ao SQL. Os nomes de tabela e coluna vêm de constantes fixas do código.

### Estratégia de idempotência

A carga é uma recarga completa dentro de uma única transação:

```
BEGIN; TRUNCATE itens_pedido, pedidos, clientes, produtos; INSERT ... (4 tabelas); COMMIT;
```

- Rodar duas vezes dá o mesmo resultado, porque cada execução substitui todo o conteúdo pelo resultado da transformação, que é determinística.
- Se algo falhar no meio, o `ROLLBACK` devolve o banco ao estado anterior, sem carga parcial.
- Escolhi essa estratégia em vez de "inserir ignorando chaves existentes" (`ON CONFLICT DO NOTHING`). Com essa outra opção, um pedido corrigido na origem nunca seria atualizado. Com 5000 pedidos, recarregar tudo leva poucos segundos.

### Evidência: duas execuções seguidas

```
=== execucao 1 ===
extracao: clientes paginas=10 registros=1000
extracao: pedidos paginas=51 registros_brutos=5100
extracao: produtos registros=12
transformacao: pedidos_unicos=5000 repetidos_descartados=100
transformacao: emails_nulos=81 estados_padronizados=151 datas_convertidas=1037 valores_convertidos=1255
transformacao: divergentes=238
carga: clientes=1000 produtos=12 pedidos=5000 itens=12455
=== execucao 2 ===
extracao: clientes paginas=10 registros=1000
extracao: pedidos paginas=51 registros_brutos=5100
extracao: produtos registros=12
transformacao: pedidos_unicos=5000 repetidos_descartados=100
transformacao: emails_nulos=81 estados_padronizados=151 datas_convertidas=1037 valores_convertidos=1255
transformacao: divergentes=238
carga: clientes=1000 produtos=12 pedidos=5000 itens=12455
```

As contagens da linha `carga:` são lidas do banco (`SELECT COUNT(*)`) depois do `COMMIT`.

Outras verificações feitas:
- **Valores no banco:** `SUM(valor_itens)` = 311228.75, 238 pedidos com `divergente`, 81 clientes com `email IS NULL`, nenhum estado em minúsculas. As datas vão de 2026-01-01 a 2026-10-28.
- **Rollback:** forcei um `produto_id` inexistente em um item. A carga falhou com `erro: carga desfeita (rollback): ... violates foreign key constraint ...`, e as contagens continuaram 12 / 1000 / 5000 / 12455.
- **Banco fora do ar** (`PGPORT=5999`): `erro: nao foi possivel conectar ao PostgreSQL em 127.0.0.1:5999 (connection timeout expired); o conteiner verdejar-pg esta rodando?`, com código de saída 1.

## Testes e reconciliação (Parte 4)

### Como rodar os testes

```
python -m pytest -v
```

A configuração está em `pytest.ini`: a pasta de testes é `tests/` e a raiz do projeto entra no `sys.path`, para que `import etl...` funcione.

- `tests/test_transformacao.py` tem 14 testes, pelo menos um por armadilha (A1 a A6). Os três obrigatórios são A3 (data), A4 (valor com vírgula) e A5 (pedido repetido). Cada teste usa uma entrada conhecida e compara com a saída esperada.
- `tests/test_reconciliacao.py` tem 3 testes que precisam do banco no ar e de `brutos/`. Antes deles, um fixture faz a carga a partir de `brutos/`. Se o banco ou os brutos não estiverem disponíveis, os testes são pulados (*skip*), com o motivo.
  - **Contagem:** os pedidos únicos da origem são iguais à contagem de linhas da tabela `pedidos`.
  - **Soma:** `valor_itens` da origem é igual a `SUM(valor_itens)` do destino, com tolerância de 1 centavo.
  - **Teste de consulta (a):** a soma dos meses é igual à soma geral da tabela, tanto em `valor_itens` quanto em `valor_total`.

Em `etl/reconciliacao.py`, o lado "origem" é recalculado direto dos JSON brutos, sem usar as funções de `transformacao.py`. Assim, um erro na transformação não aparece igual dos dois lados da conta e passa despercebido.

Os valores monetários usam `Decimal`. Por isso o teste da A4 compara com `Decimal("125.84")`, e não com o float `125.84` do exemplo do Apêndice A.

Saída do pytest:

```
$ python -m pytest -v
collected 17 items

tests/test_reconciliacao.py::test_reconciliacao_contagem_de_pedidos PASSED
tests/test_reconciliacao.py::test_reconciliacao_soma_valor_itens_tolerando_um_centavo PASSED
tests/test_reconciliacao.py::test_consulta_vendas_por_mes_soma_igual_a_soma_geral PASSED
tests/test_transformacao.py::test_a1_cliente_sem_email_e_mantido_com_email_nulo PASSED
tests/test_transformacao.py::test_a1_email_em_branco_vira_nulo PASSED
tests/test_transformacao.py::test_a2_estado_minusculo_vira_maiusculo PASSED
tests/test_transformacao.py::test_a2_estado_invalido_gera_erro PASSED
tests/test_transformacao.py::test_a3_data_iso_e_brasileira_viram_a_mesma_data PASSED
tests/test_transformacao.py::test_a3_data_em_formato_desconhecido_gera_erro PASSED
tests/test_transformacao.py::test_a4_valor_com_virgula_vira_numero PASSED
tests/test_transformacao.py::test_a4_valor_numerico_permanece_com_duas_casas PASSED
tests/test_transformacao.py::test_a4_valor_invalido_gera_erro PASSED
tests/test_transformacao.py::test_a5_pedido_repetido_fica_uma_vez_mantendo_a_primeira_ocorrencia PASSED
tests/test_transformacao.py::test_a5_aplicar_duas_vezes_nao_muda_o_resultado PASSED
tests/test_transformacao.py::test_a6_valor_itens_e_soma_de_quantidade_vezes_preco PASSED
tests/test_transformacao.py::test_a6_tolerancia_de_um_centavo PASSED
tests/test_transformacao.py::test_a6_pedido_divergente_grava_os_dois_valores_e_marca PASSED

============================= 17 passed in 2.13s ==============================
```

### Saída completa do ETL, com a reconciliação

O `python -m etl.main` termina com a reconciliação. O código de saída é 2 se origem e destino não baterem.

```
extracao: clientes paginas=10 registros=1000
extracao: pedidos paginas=51 registros_brutos=5100
extracao: produtos registros=12
transformacao: pedidos_unicos=5000 repetidos_descartados=100
transformacao: emails_nulos=81 estados_padronizados=151 datas_convertidas=1037 valores_convertidos=1255
transformacao: divergentes=238
carga: clientes=1000 produtos=12 pedidos=5000 itens=12455
reconciliacao: pedidos_origem=5000 pedidos_destino=5000
reconciliacao: soma_valor_itens_origem=311228.75 soma_valor_itens_destino=311228.75 diferenca=0.00
divergentes: 238 pedidos com valor_total diferente da soma dos itens
```

### Consultas de validação

As consultas estão em [`consultas_validacao.sql`](consultas_validacao.sql). Para rodar (PowerShell):

```
Get-Content consultas_validacao.sql | docker exec -i verdejar-pg psql -U postgres -d verdejar
```

Critério adotado: "vendas" inclui todos os pedidos carregados, inclusive os cancelados. A consulta mostra os dois valores: `total_itens` (soma de `valor_itens`, calculado) e `total_informado` (soma de `valor_total`, vindo da origem).

**(a) Total de vendas por mês**

```
   mes   | pedidos | total_itens | total_informado
---------+---------+-------------+-----------------
 2026-01 |     488 |    30355.02 |        30449.02
 2026-02 |     536 |    33855.86 |        33923.86
 2026-03 |     487 |    30617.70 |        30678.70
 2026-04 |     521 |    31170.96 |        31253.96
 2026-05 |     512 |    30777.02 |        30890.02
 2026-06 |     523 |    31557.73 |        31627.73
 2026-07 |     519 |    32685.17 |        32796.17
 2026-08 |     458 |    29260.04 |        29328.04
 2026-09 |     476 |    29909.71 |        29995.71
 2026-10 |     480 |    31039.54 |        31104.54
(10 rows)
```

**(a) Teste de consulta: soma dos meses igual à soma geral**

```
 soma_meses_itens | soma_geral_itens | itens_ok | informado_ok
------------------+------------------+----------+--------------
        311228.75 |        311228.75 | t        | t
```

Os 10 meses somam 5000 pedidos, que é o total da tabela. O mesmo teste roda automaticamente no pytest (`test_consulta_vendas_por_mes_soma_igual_a_soma_geral`).

**(b) Quantidade de pedidos por estado**

```
 estado | pedidos
--------+---------
 RS     |    1543
 SC     |    1127
 PR     |     974
 SP     |     880
 MG     |     476
(5 rows)
```

Aparecem só 5 estados, todos em maiúsculas. Isso confirma que a A2 foi tratada: sem o tratamento, `rs` e `RS` apareceriam como estados diferentes. Os 5 somam 5000 pedidos.

**(c) Pedidos divergentes**

A consulta devolve 238 linhas, o mesmo número do contador do ETL. As 5 primeiras:

```
  id  | cliente_id | data_pedido | valor_total | valor_itens | diferenca
------+------------+-------------+-------------+-------------+-----------
    1 |        303 | 2026-02-19  |      125.84 |      130.84 |     -5.00
   51 |         23 | 2026-04-27  |       26.58 |       23.58 |      3.00
   71 |        962 | 2026-05-27  |      144.35 |      134.35 |     10.00
   81 |        198 | 2026-09-05  |       -1.84 |        3.16 |     -5.00
  106 |        973 | 2026-05-02  |       47.78 |       44.78 |      3.00
...
(238 rows)
```

Distribuição das diferenças (`valor_total - valor_itens`): −5,00 em 63 pedidos, +3,00 em 88 e +10,00 em 87. Nenhuma divergência fica perto do limite de 1 centavo.

O pedido 81 é o único com `valor_total` negativo (−1,84). Os itens dele somam 3,16 e a origem informou 5,00 a menos. É um efeito da própria armadilha A6, e o pedido já está marcado como divergente. Mantive o valor informado como veio, porque a regra da A6 é sinalizar a divergência e não corrigir.
