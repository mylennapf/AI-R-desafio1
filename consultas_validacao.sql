-- Consultas de validacao do ETL da Verdejar (PostgreSQL, caminho B).
-- Rodar (PowerShell): Get-Content consultas_validacao.sql | docker exec -i verdejar-pg psql -U postgres -d verdejar
-- "Vendas" = todos os pedidos carregados, inclusive cancelados.
-- Mostramos valor_itens (calculado a partir dos itens) e valor_total (informado pela origem).

-- (a) Total de vendas por mes
SELECT TO_CHAR(DATE_TRUNC('month', data_pedido), 'YYYY-MM') AS mes,
       COUNT(*)                                             AS pedidos,
       SUM(valor_itens)                                     AS total_itens,
       SUM(valor_total)                                     AS total_informado
FROM pedidos
GROUP BY DATE_TRUNC('month', data_pedido)
ORDER BY mes;

-- (a) Teste de consulta: a soma dos meses deve ser igual a soma geral da tabela
SELECT por_mes.soma_meses_itens,
       geral.soma_geral_itens,
       por_mes.soma_meses_itens = geral.soma_geral_itens             AS itens_ok,
       por_mes.soma_meses_informado = geral.soma_geral_informado     AS informado_ok
FROM (SELECT SUM(total_itens) AS soma_meses_itens, SUM(total_informado) AS soma_meses_informado
      FROM (SELECT SUM(valor_itens) AS total_itens, SUM(valor_total) AS total_informado
            FROM pedidos GROUP BY DATE_TRUNC('month', data_pedido)) AS m) AS por_mes,
     (SELECT SUM(valor_itens) AS soma_geral_itens, SUM(valor_total) AS soma_geral_informado
      FROM pedidos) AS geral;

-- (b) Quantidade de pedidos por estado do cliente
SELECT c.estado,
       COUNT(*) AS pedidos
FROM pedidos p
JOIN clientes c ON c.id = p.cliente_id
GROUP BY c.estado
ORDER BY pedidos DESC, c.estado;

-- (c) Pedidos divergentes (valor_total diferente da soma dos itens por mais de 1 centavo)
SELECT id,
       cliente_id,
       data_pedido,
       valor_total,
       valor_itens,
       valor_total - valor_itens AS diferenca
FROM pedidos
WHERE divergente
ORDER BY id;
