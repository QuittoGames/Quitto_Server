<div align="center">

# MCP — Quitto Server

### Plataforma de orquestração e controle local (Master Control Protocol)

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---

Descrição

MCP (Master Control Protocol) é uma base modular para orquestração, controle e automação em ambientes locais e laboratórios (home-lab). O projeto fornece serviços, repositórios e utilitários para criar, testar e operar componentes controlados por um protocolo padronizado, com opções de interface web estática e execução por linha de comando.

Índice

- [Funcionalidades](#funcionalidades)
- [Arquitetura e componentes](#arquitetura-e-componentes)
- [Instalação rápida](#instalação-rápida)
- [Configuração](#configuração)
- [Execução e uso](#execução-e-uso)
- [Desenvolvimento](#desenvolvimento)
- [Contribuição](#contribuição)
- [Resolução de problemas](#resolução-de-problemas)
- [Licença](#licença)

## Funcionalidades

- Protocolo MCP: mensagens e padrões para coordenação entre serviços.
- Conjunto de serviços modulares (MCPService, MachineService, WebService).
- Interface web estática para visualização e operações básicas (pasta `web/`).
- Repositórios locais para persistência leve (pasta `Repository/`).
- Scripts auxiliares para criação e configuração de projetos.

## Arquitetura e componentes

```
Usuario  <--->  Web UI / CLI
                  |
               Services (src/Services/)
                  |
        Repositories / DB (Repository/, DB/)
                  |
              Domain Models (models/)
```

Principais diretórios:

- `src/` — código-fonte principal (serviços, orquestradores, scripts de entrypoint).
- `src/Services/` — serviços implementados (MCPService, MachineService, WebService, etc.).
- `models/` — modelos de domínio (`User`, `Machine`, `Agent`).
- `Repository/` — implementações de persistência e repositórios.
- `web/` — arquivos estáticos (HTML/CSS/JS) para controle/visualização mínima.

## Instalação rápida

Requisitos mínimos:

- Python 3.8 ou superior
- Git

Comandos rápidos:

```bash
git clone https://github.com/yourusername/mcp.git
cd mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt || true
```

Observação: alguns serviços não dependem de pacotes externos e podem ser executados diretamente com o Python instalado.

## Configuração

As configurações podem ser definidas via variáveis de ambiente ou arquivo `.env` (não comitar).

Exemplo recomendado de `.env` (na raiz do projeto):

```env
MCP_ENV=development
DB_PATH=./DB/data.sqlite
WEB_PORT=8080
```

Verifique `src/DB/DBConnection.py` e `src/Services/*` para parâmetros específicos de serviços.

## Execução e uso

Entrypoint genérico (exemplo):

```bash
python src/index.py
```

Serviços individuais podem ser executados diretamente (consulte cada módulo em `src/Services/`).

Interface web (estática): abra `web/index.html` ou inicie `WebService` para servir os arquivos via HTTP.

## Desenvolvimento

Estrutura resumida do repositório:

```
src/
├── Services/
├── DB/
└── index.py
models/
Repository/
web/
```

- Escreva testes para funcionalidades críticas antes de abrir PRs.
- Prefira commits pequenos e descritivos.

## Contribuição

Processo sugerido:

1. Fork do repositório
2. Criar branch: `git checkout -b feature/nome-da-feature`
3. Implementar e testar a alteração
4. Abrir Pull Request com descrição clara das mudanças

Inclua testes e atualize a documentação quando aplicável.

## Resolução de problemas

Serviço não inicializa:

- Verifique se o ambiente virtual está ativado.
- Confirme instalação de dependências.
- Cheque permissões do `DB_PATH` e portas em uso.

Erro de importação:

- Confirme `PYTHONPATH` e a ativação do venv.

## Links úteis

- Python: https://www.python.org/
- VS Code: https://code.visualstudio.com/

## Licença

Licenciado sob a Licença MIT. Consulte o arquivo `LICENSE` para o texto completo.

---

Este `README` foi consolidado para remover conteúdo duplicado e marcações de merge. Caso prefira, posso:

1. Tornar o texto disponível em inglês.
2. Adicionar badges de CI/cobertura (ex.: GitHub Actions).
3. Escrever quickstart específico para `MCPService`, `WebService` ou `MachineService`.

Indique a opção ou solicite outro ajuste.
