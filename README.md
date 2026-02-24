<<<<<<< HEAD
<<<<<<< HEAD
<div align="center">

# MCP — Quitto Server

### Plataforma de orquestração e controle local (Master Control Protocol)

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](https://opensource.org/licenses/MIT)

</div>

---


Descrição

MCP (Master Control Protocol) é uma plataforma modular para orquestração, controle e automação em ambientes locais e laboratórios (home-lab). O repositório inclui um servidor principal — o MCP Server — que implementa o Master Control Protocol e atua como orquestrador central do ecossistema: gerencia modelos de contexto, expõe APIs de controle, coordena serviços e mantém a coesão entre componentes.

O projeto oferece serviços, repositórios e utilitários para criar, testar e operar componentes controlados por esse protocolo, com uma interface web estática e ferramentas de linha de comando.

Índice

- [MCP — Quitto Server](#mcp--quitto-server)
    - [Plataforma de orquestração e controle local (Master Control Protocol)](#plataforma-de-orquestração-e-controle-local-master-control-protocol)
  - [Funcionalidades](#funcionalidades)
  - [Arquitetura e componentes](#arquitetura-e-componentes)
  - [Definição técnica — separando MCP e MCP Server](#definição-técnica--separando-mcp-e-mcp-server)
    - [Onde ver o código (arquivos de referência)](#onde-ver-o-código-arquivos-de-referência)
    - [Exemplo rápido: seguir o fluxo de uma requisição](#exemplo-rápido-seguir-o-fluxo-de-uma-requisição)
  - [Instalação rápida](#instalação-rápida)
  - [Configuração](#configuração)
  - [Execução e uso](#execução-e-uso)
  - [Desenvolvimento](#desenvolvimento)
  - [Contribuição](#contribuição)
  - [Resolução de problemas](#resolução-de-problemas)
  - [Links úteis](#links-úteis)
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
               Server (orquestrador)
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
- `src/server.py` or `src/index.py` — entrypoint(s) do servidor principal (MCP Server / orquestrador).
- `models/` — modelos de domínio (`User`, `Machine`, `Agent`).
- `Repository/` — implementações de persistência e repositórios.
- `web/` — arquivos estáticos (HTML/CSS/JS) para controle/visualização mínima.

Servidor principal (MCP Server)

O MCP Server implementa o Model Context Protocol e tem as responsabilidades principais:

- Gerenciar contextos de modelos e o estado global do ecossistema.
- Expor uma API de controle para clientes (CLI, UI, integrações externas).
- Orquestrar comunicação entre serviços e repositórios.
- Autenticar/autorizar requisições e aplicar políticas de operação.

Em ambientes de produção ou testes avançados, o MCP Server é o componente central que coordena operações de alto nível.

## Definição técnica — separando MCP e MCP Server

Para evitar ambiguidade: o termo "MCP" refere-se aqui ao protocolo (Master Control Protocol) — um conjunto de mensagens, comandos e modelos de contexto usados para coordenar os componentes. O "MCP Server" é a implementação concreta desse protocolo no repositório e o orquestrador que processa mensagens, mantém estado e expõe APIs.

- MCP (Master Control Protocol): especificação lógica — formatos de mensagem, contratos dos modelos de contexto, comandos e eventos.
- MCP Server: implementação do protocolo, responsável por interpretar mensagens MCP, aplicar regras de negócio, coordenar serviços e persistir estado.

### Onde ver o código (arquivos de referência)

- Entrypoint / orquestrador: [src/index.py](src/index.py)
- Implementação do protocolo MCP: [src/Services/MCP/MCPService.py](src/Services/MCP/MCPService.py)
- Estado em memória / gerenciamento de contexto: [src/Services/MCP/MemoryService.py](src/Services/MCP/MemoryService.py)
- Serviço web (frontend / APIs): [src/Services/WebService.py](src/Services/WebService.py)
- Conexão com banco/armazenamento: [src/DB/DBConnection.py](src/DB/DBConnection.py)
- Repositórios de exemplo (máquinas, usuários): [Repository/Machines/MachineRepository.py](Repository/Machines/MachineRepository.py) e [Repository/User/UserRepository.py](Repository/User/UserRepository.py)

Leia os arquivos acima para acompanhar como o protocolo é definido (tipos, mensagens) e como o servidor processa essas mensagens em runtime.

### Exemplo rápido: seguir o fluxo de uma requisição

1. Cliente (CLI ou Web UI) envia uma requisição para criar/atualizar um contexto.
2. O MCP Server (entrypoint) recebe a requisição e a encaminha para `MCPService`.
3. `MCPService` valida a mensagem segundo o protocolo MCP e usa `MemoryService` / repositórios para atualizar o estado.
4. Resultado é persistido via `src/DB/DBConnection.py` / `Repository/*` e uma resposta é retornada ao cliente.

Para testar localmente, inicie o servidor e observe logs/prints no fluxo acima:

```bash
python src/index.py
```

Em seguida, abra `web/index.html` ou use um cliente HTTP/CLI para enviar comandos ao MCP Server.

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

Entrypoint genérico / servidor principal

O servidor principal (orquestrador MCP) pode ser iniciado a partir do entrypoint do projeto. Exemplos:

```bash
# Inicia o servidor principal (se presente)
python src/server.py

# Alternativa: alguns distribuídos usam index.py como entrypoint
python src/index.py
```

Serviços individuais podem ser executados diretamente para testes isolados (consulte cada módulo em `src/Services/`).

Interface web (estática)

Abra `web/index.html` via servidor estático simples ou execute `WebService` para servir os arquivos via HTTP, permitindo que o MCP Server sirva APIs e o frontend consuma dados.

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
=======
# Quitto_Server
Home Lab and MCP Server
>>>>>>> c52c977 (Initial commit)
=======
# Quitto_Server
Home Lab and MCP Server
>>>>>>> a9f956a7d1c187fa970b0bf4a93f25cf8324dc97
