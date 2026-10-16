# Fluxo — Painel de Estoque e Expedição

Aplicação web demonstrativa para acompanhar produtos, registrar entradas e saídas de materiais e analisar a posição do estoque. O projeto usa uma situação fictícia inspirada em rotinas de expedição; nenhum dado de empregadores, clientes ou operações reais é utilizado.

## Demonstração

Na primeira execução, o sistema cria um banco SQLite local e carrega produtos fictícios para que o painel abra com dados de exemplo. Você pode cadastrar produtos, registrar movimentações, pesquisar e filtrar o catálogo, consultar alertas de reposição e exportar o histórico para CSV.

## Funcionalidades

- Cadastro de produtos com SKU único, categoria, unidade, saldo inicial e nível mínimo.
- Registro de entradas e saídas com observação opcional e data/hora local.
- Bloqueio de saída maior que o saldo disponível.
- Indicadores de produtos, unidades em estoque, alertas e movimentações.
- Pesquisa por nome, SKU ou categoria e filtro por categoria.
- Alertas visuais quando o saldo chega ao nível mínimo ou fica abaixo dele.
- Resumo de unidades por categoria.
- Histórico recente e exportação integral de movimentações em CSV compatível com Excel.
- Interface adaptável a computador e celular, com labels acessíveis e estados de foco.
- Testes automatizados para as regras centrais.

## Tecnologias

- Python 3.10 ou superior
- Flask
- SQLite
- HTML semântico, CSS responsivo e JavaScript simples
- `unittest` para testes

## Executar localmente

No terminal, dentro desta pasta:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Abra `http://127.0.0.1:5000` no navegador. Se o comando `py` não estiver disponível, use `python` no lugar.

O banco local é criado em `instance/estoque.db` na primeira execução. Esse arquivo é ignorado pelo Git para que dados locais não sejam publicados.

## Testes

Com as dependências instaladas, execute:

```powershell
py -m unittest discover -s tests -v
```

Os testes cobrem inicialização com dados de demonstração, entradas e saídas, prevenção de estoque negativo, rejeição de SKU duplicado, validação de quantidades fora do limite do SQLite e neutralização de fórmulas na exportação CSV.

## Demonstração online

O arquivo `render.yaml` configura uma publicação gratuita no Render com Gunicorn, verificação de saúde e modo somente leitura. Depois que o serviço estiver conectado ao repositório no Render, os próximos commits na branch `main` podem atualizar a demonstração automaticamente. No plano gratuito, o serviço pode suspender após inatividade e o sistema de arquivos é temporário; por isso, o banco de demonstração é recriado e qualquer alteração local se perde. Os formulários de cadastro e movimentação ficam desativados na versão online.

## Estrutura

```text
app.py                         rotas, validações e acesso ao SQLite
templates/index.html           painel e formulários
static/styles.css              identidade visual responsiva
static/app.js                  pequenos aprimoramentos de interface
tests/test_app.py              testes das regras de negócio
docs/relatorio-tecnico.md      relatório técnico do projeto
requirements.txt               dependências Python
render.yaml                    configuração de hospedagem no Render
```

## Regras e limites do protótipo

- Quantidades são números inteiros e não podem ficar negativas.
- Cada SKU é único, sem diferenciar maiúsculas de minúsculas.
- O sistema não tem autenticação, perfis de acesso ou integração com ERP; é um protótipo local para portfólio.
- As movimentações usam dados fictícios de demonstração. Antes de uso real, seriam necessários autenticação, proteção CSRF, trilha de auditoria, cópias de segurança, política de retenção e revisão de segurança.
- O valor de `SECRET_KEY` padrão serve apenas ao uso local. Uma implantação real deve definir uma chave forte em variável de ambiente, proteger o serviço e usar uma base de dados adequada ao ambiente.

## Próximas evoluções

1. Adicionar paginação e filtros por período.
2. Criar fluxo de autorização para ajustes e cancelamentos, preservando o histórico.
3. Incluir níveis de usuário e proteção CSRF.
4. Adicionar testes de integração para formulários inválidos e filtros.
5. Implantar uma demonstração em serviço compatível com Flask, com banco persistente e dados apenas fictícios.

## Autor

Samuel Sampaio — estudante de Análise e Desenvolvimento de Sistemas. Projeto educacional para demonstrar fundamentos de desenvolvimento web, banco de dados, lógica de programação e análise operacional.
