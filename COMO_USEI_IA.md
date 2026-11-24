# COMO_USEI_IA.md

**Ferramenta utilizada:** Kiro (assistente de IA integrado ao IDE)

A IA foi utilizada como ferramenta de apoio durante o desenvolvimento do ETL, principalmente para esclarecer dúvidas sobre Python, sugerir implementações pontuais e auxiliar na criação de testes automatizados.

As decisões de implementação, execução, análise dos resultados e validação do comportamento do código foram realizadas por mim.

## 1. Sugestões aceitas

### 1.1. Conversão e padronização de datas (A3)

**Contexto:** Durante a transformação dos pedidos, identifiquei que as datas recebidas da API poderiam estar em dois formatos diferentes: `AAAA-MM-DD` e `DD/MM/AAAA`.

**O que pedi à IA:**

"Como posso criar uma função em Python que receba uma data como string, identifique se está no formato AAAA-MM-DD ou DD/MM/AAAA e retorne a data padronizada no formato AAAA-MM-DD?"

**Sugestão apresentada:**

Utilizar o módulo `datetime` para tentar os dois formatos com `strptime()`, um de cada vez, e devolver um objeto `date` (função `converter_data`). Formatos desconhecidos geram `ValueError` com mensagem clara.

Em vez de devolver um texto `AAAA-MM-DD`, a função devolve `date`, porque a coluna `data_pedido` do banco é do tipo `DATE` e o `psycopg` converte `date` para esse tipo automaticamente.

**Por que aceitei:**

A solução utilizava recursos da biblioteca padrão do Python, era simples de compreender e permitia separar a transformação em uma função independente, facilitando sua reutilização e seus testes.

**Como validei:**

Executei a função com entradas nos dois formatos e confirmei que `"2026-02-19"` e `"19/02/2026"` resultam em `date(2026, 2, 19)`. Esses casos viraram os testes `test_a3_data_iso_e_brasileira_viram_a_mesma_data` e `test_a3_data_em_formato_desconhecido_gera_erro`. Após a carga, conferi no banco que as datas vão de 2026-01-01 a 2026-10-28, sem valores fora do esperado.

---

### 1.2. Conversão de valores monetários (A4)

**Contexto:** Os pedidos apresentavam valores totais em formatos diferentes: alguns como números e outros como strings utilizando vírgula como separador decimal.

**O que pedi à IA:**

"Preciso de uma função que receba um valor numérico ou uma string com vírgula decimal, como '125,84', e retorne um número com duas casas decimais. Como tratar esses dois casos sem duplicar código?"

**Sugestão apresentada:**

Verificar o tipo do valor recebido e, quando necessário, substituir a vírgula por ponto antes de realizar a conversão numérica.

**Por que aceitei:**

A abordagem centralizava a conversão em uma única função, evitando repetir a mesma lógica em diferentes partes do ETL.

**Como validei:**

Testei entradas numéricas e strings com vírgula decimal, conferindo se os valores convertidos correspondiam aos resultados esperados. Também verifiquei a consistência dos valores utilizados posteriormente no cálculo de `valor_itens`.

---

### 1.3. Geração do campo `linha` dos itens do pedido

**Contexto:** A API retorna os itens como uma lista dentro de cada pedido, com `produto_id`, `quantidade` e `preco_unitario`, mas sem um campo `linha`. A tabela `itens_pedido` exige `(pedido_id, linha)` como chave primária composta.

**O que perguntei à IA:**

Se a API deveria mandar o campo `linha` e não estava mandando.

**Sugestão apresentada:**

A IA explicou que não se trata de um erro da API: as duas estruturas têm responsabilidades diferentes. Na API, a posição na lista já identifica o item; o banco precisa de um número explícito. A sugestão foi gerar a `linha` na transformação, a partir da posição de cada item (primeiro item = linha 1, segundo = linha 2, e assim por diante), na função `transformar_itens`.

**Por que aceitei:**

A adequação da estrutura de origem à de destino é responsabilidade do ETL. Também avaliei usar `produto_id` como parte da chave e descartei, porque o mesmo produto pode aparecer mais de uma vez no mesmo pedido, o que causaria conflito na chave primária. A numeração pela posição sempre funciona e é determinística: como a ordem da API é fixa, novas execuções geram as mesmas linhas, o que é importante para a idempotência.

**Como validei:**

A carga de 12455 itens passou sem violar a chave primária `(pedido_id, linha)`. O teste `test_a6_pedido_divergente_grava_os_dois_valores_e_marca` confere que os três itens do pedido 1 recebem as linhas `[1, 2, 3]`. A regra está documentada no `CONTRATO_DE_DADOS.md`.

## 2. Sugestões rejeitadas

### 2.1. Remover clientes sem e-mail (A1)

**Contexto:** Ao analisar os dados da API, alguns clientes apresentavam o campo de e-mail nulo.

**O que pedi à IA:**

"Como posso tratar registros de clientes que chegam sem e-mail durante a transformação dos dados?"

**Sugestão apresentada:**

Uma das abordagens sugeridas foi filtrar os registros e remover aqueles que não possuíam e-mail preenchido.

**Por que rejeitei:**

Essa abordagem não respeitava a regra de negócio definida no desafio. A ausência de e-mail não significa que o cliente seja inválido. O requisito determina que o cliente deve ser mantido, com o campo de e-mail gravado como nulo.

**O que fiz no lugar:**

Mantive todos os registros e tratei os e-mails ausentes sem descartar os clientes, contabilizando a quantidade de valores nulos encontrados.

**Como validei:**

Comparei a quantidade de clientes extraídos com a quantidade carregada no banco e conferi a presença dos registros com e-mail nulo.

---

### 2.2. Utilização de comparação direta de valores decimais (A6)

**Contexto:** Durante a implementação da identificação de pedidos divergentes, precisei comparar o valor total informado pela API com a soma dos itens do pedido.

**O que pedi à IA:**

"Como posso identificar pedidos em que o valor_total informado é diferente da soma de quantidade vezes preco_unitario dos itens?"

**Sugestão apresentada:**

A IA sugeriu realizar a comparação direta entre os valores calculados e os valores informados.

**Por que rejeitei:**

A comparação direta de números decimais pode apresentar problemas de precisão, especialmente em cálculos envolvendo valores monetários. Além disso, o desafio estabelece uma tolerância de um centavo para identificar divergências.

**O que fiz no lugar:**

Adotei uma comparação considerando a diferença entre os valores e o limite de tolerância de R$ 0,01, mantendo os dois valores registrados para possibilitar a conferência.

**Como validei:**

Comparei os resultados da implementação com casos de pedidos em que os valores coincidiam e casos em que apresentavam divergências superiores à tolerância estabelecida.

## 3. Falhas e retrabalho

### 3.1. Comando do Docker falhou por porta ocupada (Parte 0)

**Contexto:** Para subir o PostgreSQL pelo caminho B, a IA propôs o comando do documento do desafio, com `-p 5432:5432`.

**Falha encontrada:**

O contêiner foi criado, mas não subiu. O erro foi:

```
Bind for 0.0.0.0:5432 failed: port is already allocated
```

Em seguida, a aplicação do esquema falhou com `container ... is not running`.

**Causa:**

A porta 5432 já estava ocupada pelo PostgreSQL de outro projeto meu, também em Docker. A IA não verificou se a porta estava livre antes de propor o comando.

**O que fiz para corrigir:**

Em vez de parar o outro projeto, removi o contêiner com falha e recriei com `-p 5433:5432`, mapeando o banco do Verdejar para a porta 5433 do computador. Atualizei `PGPORT=5433` no `.env` e no `.env.example` e registrei o motivo no README.

**Como validei:**

Apliquei o `schema.sql` no contêiner `verdejar-pg` e conferi com `\dt` que as quatro tabelas foram criadas (clientes, itens_pedido, pedidos e produtos).

---

### 3.2. Teste do erro de conexão não testava nada (Parte 1)

**Contexto:** Para provar que a extração trata o erro de conexão, a IA trocou a variável `URL_BASE` do módulo `etl.extracao` por uma porta sem API (8999) e chamou `main()`.

**Falha encontrada:**

Em vez de mostrar a mensagem de erro, a extração rodou normalmente contra a porta 8000 e imprimiu os contadores. O teste parecia ter passado, mas não tinha testado o caso de erro.

**Causa:**

A função era `def extrair_tudo(url_base=URL_BASE)`. Em Python, o valor padrão de um parâmetro é calculado uma única vez, quando a função é definida. Trocar a variável depois não muda esse valor padrão.

**O que fiz para corrigir:**

A URL da API passou a vir da variável de ambiente `VERDEJAR_API_URL`, com `http://127.0.0.1:8000` como padrão. Assim, dá para apontar para outra porta sem mexer no código.

**Como validei:**

Rodei com `VERDEJAR_API_URL=http://127.0.0.1:8999` e o programa imprimiu `erro: nao foi possivel conectar em http://127.0.0.1:8999 (...); a API esta rodando?`, com código de saída 1. Sem a variável, a extração voltou a ler as 10 páginas de clientes e as 51 de pedidos.

---

### 3.3. Teste da A4 falhou ao comparar `Decimal` com `float`

**Contexto:** Escrevi o teste da armadilha A4 seguindo o exemplo do Apêndice A do desafio, que compara o resultado de `converter_valor` com o número `125.84`.

**Falha encontrada:**

Ao rodar `python -m pytest`, o teste `test_a4_valor_com_virgula_vira_numero` falhou com a mensagem:

```
>       assert converter_valor("125,84") == 125.84
E       AssertionError: assert Decimal('125.84') == 125.84
E        +  where Decimal('125.84') = converter_valor('125,84')
```

**Causa:**

A função `converter_valor` devolve `Decimal`, e não `float`. O `float` não guarda 125,84 exatamente: internamente o valor é `125.840000000000003410605131648480892181396484375`. Por isso, `Decimal('125.84') == 125.84` resulta em `False`.

O uso de `Decimal` é proposital. Valores monetários em `float` acumulam erros de arredondamento ao somar milhares de pedidos, e isso atrapalharia a reconciliação, que precisa resultar em `diferenca=0.00`.

**O que fiz para corrigir:**

Corrigi o teste, e não a função, porque a função estava com o comportamento correto. O valor esperado passou a ser do mesmo tipo devolvido pela função:

```python
assert converter_valor("125,84") == Decimal("125.84")
```

**Como validei:**

Rodei `python -m pytest` novamente e todos os testes passaram (`17 passed`). A reconciliação do ETL continuou com `diferenca=0.00`.

---

## 4. Considerações finais

A utilização da IA foi importante principalmente para acelerar a compreensão de problemas específicos e explorar alternativas de implementação.

Durante o desenvolvimento, percebi que uma sugestão aparentemente correta nem sempre atende aos requisitos do problema. Por isso, procurei avaliar cada resposta considerando as regras do desafio e de negócio, a qualidade dos dados e o comportamento esperado do ETL.

A IA foi utilizada como ferramenta de apoio, mas a responsabilidade pelas decisões técnicas, implementação, correções e validação dos resultados permaneceu comigo.