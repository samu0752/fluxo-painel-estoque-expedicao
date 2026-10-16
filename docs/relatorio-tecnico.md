# Relatório Técnico — Fluxo: Painel de Estoque e Expedição

**Autor:** Samuel Sampaio  
**Tipo:** Projeto demonstrativo de portfólio  
**Tecnologias:** Python, Flask, SQLite, HTML, CSS e JavaScript  
**Estado:** Protótipo funcional local

## 1. Resumo executivo

O Fluxo é uma aplicação web para demonstrar o registro e o acompanhamento de materiais em um processo simplificado de estoque e expedição. A aplicação mantém um catálogo de produtos, registra entradas e saídas, apresenta indicadores operacionais, sinaliza níveis de estoque que precisam de atenção e permite exportar o histórico em CSV.

O problema que o protótipo aborda é comum em rotinas operacionais: encontrar rapidamente o saldo de um item, registrar a movimentação correspondente e conferir quais itens estão próximos do limite mínimo. O projeto transforma esse fluxo em uma aplicação pequena, com regras explícitas e uma interface única para consulta e atualização.

Todos os registros que acompanham a aplicação são fictícios. O sistema não representa dados de uma empresa ou de um empregador específico.

## 2. Objetivos

### 2.1 Objetivo principal

Construir uma aplicação simples e compreensível que demonstre fundamentos de programação web, persistência de dados, validação de entrada e produção de indicadores operacionais.

### 2.2 Objetivos específicos

- Cadastrar produtos com código único e saldo mínimo de reposição.
- Registrar movimentações de entrada e saída com data, hora e observação.
- Impedir saídas superiores ao saldo disponível.
- Resumir quantidades e alertas em um painel visual.
- Permitir pesquisa e filtragem da lista de produtos.
- Exportar as movimentações para um formato que possa ser aberto em planilhas.
- Documentar a arquitetura, as regras, os limites e os testes.

## 3. Escopo funcional

### 3.1 Catálogo

Cada produto possui SKU, nome, categoria, quantidade atual, limite mínimo, unidade de medida e data de criação. O SKU é único e normalizado para maiúsculas ao cadastrar. O saldo inicial positivo gera também um registro de entrada, mantendo a relação entre posição atual e histórico.

### 3.2 Movimentações

Uma movimentação é uma entrada ou saída associada a um produto. O registro contém quantidade inteira positiva, observação opcional e data/hora local. Entradas somam unidades ao saldo; saídas subtraem unidades.

### 3.3 Indicadores e consulta

O painel calcula a quantidade de produtos cadastrados, total de unidades, número de produtos no limite mínimo ou abaixo dele e número total de movimentações. A consulta aceita busca por SKU, nome ou categoria, além de filtro por categoria. Um resumo visual apresenta unidades agrupadas por categoria.

### 3.4 Exportação

O relatório CSV inclui data/hora, tipo, SKU, produto, categoria, quantidade, unidade e observação. O arquivo usa separador ponto e vírgula e BOM UTF-8 para facilitar a abertura em planilhas em português. Campos textuais cujo primeiro caractere não branco seja um marcador de fórmula são neutralizados para reduzir o risco de execução de fórmulas ao abrir o arquivo.

## 4. Arquitetura da solução

O projeto usa uma arquitetura enxuta com três partes principais:

1. **Camada web:** Flask recebe as requisições HTTP, valida os formulários, executa as operações e renderiza a página com Jinja.
2. **Persistência:** SQLite mantém produtos e movimentações em duas tabelas relacionadas por chave estrangeira.
3. **Apresentação:** HTML organiza os conteúdos; CSS define o layout responsivo; JavaScript realiza apenas um aprimoramento discreto de interface.

O uso de SQLite mantém a instalação simples e suficiente para um protótipo local. A aplicação usa consultas parametrizadas para entradas dos formulários e ativa a verificação de chaves estrangeiras em cada conexão.

Para a demonstração online, `render.yaml` define um serviço Flask com Gunicorn e um endpoint de saúde. A variável `READ_ONLY_DEMO` oculta os formulários e bloqueia operações de cadastro e movimentação. Essa configuração evita que visitantes alterem os dados compartilhados. O serviço gratuito do Render usa armazenamento temporário e pode suspender quando fica sem tráfego; os dados fictícios são semeados novamente quando a aplicação inicia.

## 5. Modelo de dados

### `products`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | inteiro | Chave primária autoincremental |
| `sku` | texto | Obrigatório e único |
| `name` | texto | Obrigatório |
| `category` | texto | Obrigatório |
| `quantity` | inteiro | Não pode ser negativo |
| `minimum_quantity` | inteiro | Não pode ser negativo |
| `unit` | texto | Unidade apresentada no painel |
| `created_at` | texto | Data/hora em ISO 8601 com fuso |

### `movements`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | inteiro | Chave primária autoincremental |
| `product_id` | inteiro | Chave estrangeira para `products.id` |
| `movement_type` | texto | Apenas `entrada` ou `saida` |
| `quantity` | inteiro | Estritamente maior que zero |
| `note` | texto | Observação opcional |
| `created_at` | texto | Data/hora em ISO 8601 com fuso |

Índices auxiliam consultas ordenadas por data e consultas por produto. A movimentação preserva o evento realizado; o saldo atual fica armazenado no produto e é atualizado junto com o evento.

## 6. Regras de negócio e validações

- Campos obrigatórios são conferidos antes da gravação.
- Quantidades são convertidas para números inteiros dentro do limite de 64 bits do SQLite; valores negativos, zero em movimentações, valores não inteiros e números fora desse limite são rejeitados.
- O código SKU é convertido para maiúsculas e a restrição única do banco impede duplicatas.
- Uma saída é cancelada se exceder o saldo disponível.
- A atualização do saldo e a gravação do movimento ocorrem na mesma transação de banco de dados. Em caso de erro, ambas são revertidas.
- Texto é renderizado por templates com escape automático do Jinja.
- Os campos de CSV são protegidos quando, após espaços iniciais, começam com marcadores que planilhas podem interpretar como fórmulas.
- O banco de demonstração é mantido fora do controle de versão por meio do `.gitignore`.

## 7. Interface e acessibilidade

A interface usa uma hierarquia visual de painel operacional, cartões de indicadores, tabela de produtos, resumo por categoria e formulários de ação. Cores distinguem situações de estoque, enquanto rótulos textuais mantêm o significado compreensível sem depender apenas da cor.

Os formulários têm rótulos associados, campos com restrições nativas, mensagens de estado anunciadas por região `aria-live`, foco visível e uma regra de movimento reduzido. O layout se adapta a telas menores, com tabela em área rolável e colunas reorganizadas.

## 8. Testes

A suíte baseada em `unittest` cria um banco temporário e verifica:

- inicialização da página e inclusão dos dados fictícios;
- atualização do saldo e registro de uma saída válida;
- bloqueio de uma saída maior que o saldo;
- rejeição de SKU duplicado e de quantidades fora do limite do SQLite;
- registro de entrada correspondente ao saldo inicial do produto;
- geração de CSV com cabeçalho, conteúdo, codificação adequada e proteção contra fórmulas precedidas por espaços;
- modo público de somente leitura, incluindo bloqueio de gravações pelas rotas.

Execute com `python -m unittest discover -s tests -v` depois de instalar as dependências do arquivo `requirements.txt`.

## 9. Como executar

1. Criar um ambiente virtual com `py -m venv .venv`.
2. Ativar com `.venv\Scripts\Activate.ps1` no PowerShell.
3. Instalar Flask com `py -m pip install -r requirements.txt`.
4. Iniciar a aplicação com `py app.py`.
5. Acessar `http://127.0.0.1:5000`.

O SQLite é criado na pasta local `instance/` na primeira inicialização. Os produtos iniciais servem apenas para demonstração.

## 10. Limitações e segurança

Este projeto é um protótipo educacional local. Não possui autenticação, autorização, proteção CSRF, trilha de auditoria imutável, cópias de segurança, controle de concorrência de múltiplos usuários em produção ou integração com sistemas externos. A chave padrão do Flask é apenas para desenvolvimento. O serviço de desenvolvimento (`debug=True`) não deve ser exposto à internet.

Antes de implantação ou uso operacional real, seria necessário revisar arquitetura, proteção de formulários, autenticação, política de acesso, armazenamento, recuperação de dados, monitoramento, tratamento de erros e gestão de segredos.

## 11. Evoluções propostas

1. Incluir autenticação e perfis com permissões distintas.
2. Adicionar proteção CSRF e limitação de tentativas nas operações.
3. Implementar paginação, ordenação e filtros por intervalo de datas.
4. Criar uma visão mensal de entradas, saídas e produtos mais movimentados.
5. Incluir fluxo de ajuste com justificativa e trilha de auditoria preservada.
6. Gerar testes para campos inválidos, exportação e cenários concorrentes.
7. Implantar a demonstração em infraestrutura apropriada, sem dados reais e com segredos em variáveis de ambiente.

## 12. Competências demonstradas

- Lógica de programação e validação de regras.
- Desenvolvimento web com Python e Flask.
- Modelagem relacional básica e consultas SQL.
- Integração de formulários, templates e persistência.
- Análise de indicadores operacionais e exportação de dados.
- Testes automatizados e documentação técnica.
- Considerações iniciais de acessibilidade, segurança e privacidade.
