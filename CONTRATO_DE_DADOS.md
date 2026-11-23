# Contrato de dados: ETL da Verdejar

Origem: API local (`/clientes`, `/pedidos`) e `insumos/dados/produtos.csv`. Destino: PostgreSQL, tabelas de `insumos/schema.sql`.
As funções citadas estão em `etl/transformacao.py`.

Regras gerais:
- Textos têm espaços nas pontas removidos (`strip`).
- Valores monetários são `Decimal` arredondados para 2 casas (meio para cima) e gravados como `NUMERIC`. Não usamos `float`, para evitar erro de arredondamento binário.
- Um registro que viole o contrato (data em formato desconhecido, valor não numérico, sigla de estado inválida) interrompe a transformação com mensagem `erro: ...`, sem carga parcial.

## clientes

| Campo | Tipo (destino) | Nulo? | Origem | Regra de transformação |
|---|---|---|---|---|
| id | INTEGER, PK | não | `id` | inteiro, sem mudança |
| nome | TEXT | não | `nome` | `strip` |
| email | TEXT | **sim** | `email` | **A1** (`tratar_email`): ausente, `null` ou em branco vira `NULL`; o cliente é mantido e contado em `emails_nulos` |
| cidade | TEXT | não | `cidade` | `strip` |
| estado | CHAR(2) | não | `estado` | **A2** (`padronizar_estado`): sempre em maiúsculas (`rs` vira `RS`), exatamente 2 letras; contado em `estados_padronizados` |
| cadastro_em | DATE | não | `cadastro_em` | `converter_data` (mesma regra da A3) |

## produtos

| Campo | Tipo (destino) | Nulo? | Origem | Regra de transformação |
|---|---|---|---|---|
| produto_id | INTEGER, PK | não | `produto_id` (CSV, texto) | convertido para inteiro |
| nome | TEXT | não | `nome` | `strip` |
| categoria | TEXT | não | `categoria` | `strip` |
| preco_base | NUMERIC(10,2) | não | `preco_base` (CSV, texto) | `converter_valor`, 2 casas |

## pedidos

| Campo | Tipo (destino) | Nulo? | Origem | Regra de transformação |
|---|---|---|---|---|
| id | INTEGER, PK | não | `id` | **A5** (`remover_repetidos`): um pedido por id, mantendo a primeira ocorrência na ordem das páginas; descartes contados em `repetidos_descartados` |
| cliente_id | INTEGER, FK → clientes.id | não | `cliente_id` | inteiro; precisa existir em `clientes` |
| data_pedido | DATE | não | `data_pedido` | **A3** (`converter_data`): aceita `AAAA-MM-DD` e `DD/MM/AAAA`; as que estavam em `DD/MM/AAAA` são contadas em `datas_convertidas` |
| status | TEXT | não | `status` | `strip` (valores vistos: `entregue`, `em_transporte`, `cancelado`) |
| valor_total | NUMERIC(12,2) | não | `valor_total` | **A4** (`converter_valor`): número ou texto com vírgula decimal (`"125,84"` vira `125.84`), 2 casas; os que vieram como texto são contados em `valores_convertidos` |
| valor_itens | NUMERIC(12,2) | não | calculado | **A6** (`calcular_valor_itens`): soma de `quantidade × preco_unitario` dos itens do pedido, 2 casas |
| divergente | BOOLEAN | não | calculado | **A6** (`is_divergente`): `TRUE` quando `|valor_total − valor_itens| > 0,01`; contado em `divergentes` |

Os dois valores, `valor_total` (informado) e `valor_itens` (calculado), são gravados. A divergência é sinalizada, não corrigida.

## itens_pedido

| Campo | Tipo (destino) | Nulo? | Origem | Regra de transformação |
|---|---|---|---|---|
| pedido_id | INTEGER, FK → pedidos.id | não | `id` do pedido pai | herdado do pedido |
| linha | INTEGER | não | gerado | posição do item no pedido, de 1 a N, na ordem da API (a API não envia esse campo) |
| produto_id | INTEGER, FK → produtos.produto_id | não | `itens[].produto_id` | inteiro; precisa existir em `produtos` |
| quantidade | INTEGER | não | `itens[].quantidade` | inteiro |
| preco_unitario | NUMERIC(10,2) | não | `itens[].preco_unitario` | `converter_valor`, 2 casas |

Chave primária: `(pedido_id, linha)`. Só entram os itens dos pedidos únicos. Os itens das cópias repetidas são descartados junto com o pedido.
