<<<<<<< HEAD
```markdown
# ✨ MCP: Protocolo e Ferramentas de Controle para VS Code

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-v1.0.0-blue?style=for-the-badge)](https://github.com/yourusername/mcp/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](https://opensource.org/licenses/MIT)

## 📖 Sobre o Projeto

MCP (Master Control Protocol) é uma solução abrangente projetada para integrar um protocolo de controle global, uma ferramenta de criação de projetos e um servidor dedicado diretamente no ambiente Visual Studio Code. Este projeto visa facilitar o desenvolvimento e a gestão de sistemas de controle, permitindo que desenvolvedores e equipes colaborem de forma eficiente e otimizada, tudo a partir do seu ambiente de desenvolvimento favorito.

Com o MCP, você pode definir, gerenciar e interagir com protocolos de controle complexos, gerar novos projetos de forma estruturada e hospedar um servidor de controle local, tudo dentro do fluxo de trabalho do VS Code.

## 🚀 Demonstração

Veja o MCP em ação:

![Demonstração do MCP](https://via.placeholder.com/800x450/007ACC/FFFFFF?text=Demonstração+do+MCP+-+Em+Breve)

## ✨ Funcionalidades

O MCP oferece um conjunto poderoso de funcionalidades para aprimorar seu trabalho com protocolos de controle no VS Code:

*   **Protocolo de Controle MCP:** Um protocolo robusto e flexível para comunicação e gestão global de sistemas.
*   **Criador de Projetos Integrado:** Gere novos projetos MCP e estruture-os automaticamente diretamente dentro do VS Code, acelerando o início de novos desenvolvimentos.
*   **Servidor MCP Dedicado:** Um servidor embutido para hospedar e gerenciar instâncias do protocolo, permitindo testes e simulações em tempo real.
*   **Integração Profunda com VS Code:** Projetado para ser uma extensão ou ferramenta complementar que aprimora drasticamente o fluxo de trabalho dos desenvolvedores no Visual Studio Code.

## 🛠️ Instalação

Siga estes passos para configurar o MCP em seu ambiente local.

### Pré-requisitos

Certifique-se de ter o Python 3.8+ instalado em sua máquina.

### Passos de Instalação

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/yourusername/mcp.git
    cd mcp
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    python -m venv venv
    # No Windows
    .\venv\Scripts\activate
    # No macOS/Linux
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

## 💡 Como Usar

Após a instalação, você pode começar a usar as ferramentas MCP.

### Iniciar o Servidor MCP

Para iniciar o servidor de controle MCP:

```bash
python src/server.py
```

O servidor será iniciado e aguardará conexões conforme definido no protocolo.

### Usar o Criador de Projetos

Para gerar um novo projeto MCP:

```bash
python src/creator.py create meu_novo_projeto_mcp
```

Isso criará uma nova estrutura de pastas para `meu_novo_projeto_mcp` com os arquivos iniciais necessários, seguindo o padrão MCP.

### Interagir com o Protocolo (Exemplo)

Detalhes sobre como interagir com o protocolo serão fornecidos na documentação ou podem ser explorados nos exemplos dentro da pasta `src/protocol/`.

## 📁 Estrutura de Pastas

A estrutura do projeto MCP é organizada da seguinte forma:

```
.
├── src/                      # Código-fonte principal do projeto
│   ├── __init__.py           # Inicialização do pacote Python
│   ├── protocol/             # Implementação do protocolo de controle MCP
│   │   ├── __init__.py
│   │   └── core.py           # Lógica principal do protocolo
│   │   └── messages.py       # Definição das mensagens do protocolo
│   ├── server.py             # Script do servidor MCP
│   └── creator.py            # Script da ferramenta criadora de projetos
├── tests/                    # Testes unitários e de integração
│   ├── __init__.py
│   └── test_*.py
├── docs/                     # Documentação adicional (API, guias)
├── .gitignore                # Arquivos a serem ignorados pelo Git
├── LICENSE                   # Informações da licença
├── README.md                 # Este arquivo
└── requirements.txt          # Dependências do projeto Python
```

## ⚙️ Tecnologias Utilizadas

*   **Python:** A linguagem de programação principal para o desenvolvimento do protocolo, servidor e criador.
*   **Visual Studio Code:** O ambiente de desenvolvimento alvo para integração e uso das ferramentas MCP.

## 🤝 Contribuição

Contribuições são **muito bem-vindas**! Se você deseja contribuir para o desenvolvimento do MCP, por favor, siga os passos abaixo:

1.  Faça um fork do repositório.
2.  Crie uma nova branch (`git checkout -b feature/sua-feature`).
3.  Faça suas alterações e adicione testes, se aplicável.
4.  Commit suas mudanças (`git commit -m 'feat: Adiciona nova feature X'`).
5.  Envie para a branch (`git push origin feature/sua-feature`).
6.  Abra um Pull Request detalhando suas alterações.

Por favor, certifique-se de seguir as diretrizes de estilo de código e testes.

## 📄 Licença

Este projeto está licenciado sob a Licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

```
MIT License

Copyright (c) 2023 Seu Nome ou Organização

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
<div align="center">

# ✨ MCP — Quitto Server

### Terminal-first tools & local control for Home-Lab

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](https://opensource.org/licenses/MIT)

Projeto para orquestração e controle local baseado no "Master Control Protocol" (MCP). Ideal para home-labs e ambientes de desenvolvimento que precisam de serviços controláveis localmente e integráveis ao fluxo de trabalho.

[Features](#features) • [Arquitetura](#arquitetura) • [Instalação](#instalação) • [Configuração](#configuração) • [Uso](#uso) • [Contribuição](#contribuição) • [Licença](#licença)

</div>

---

## Features

- Performance e simplicidade: serviços em Python com organização modular.
- Protocolo MCP: mensagens padronizadas para coordenação entre componentes.
- Ferramentas de criação de projetos e setup (scripts em `src/Services/SetupProjectService.py`).
- Interface web mínima em `web/` para visualização e controle rápido.
- Repositórios locais para persistência leve (pasta `Repository/`).

## Arquitetura

```
┌─────────────────────────────────────────────┐
│                   Usuário                    │
└──────────────────┬──────────────────────────┘
           │  Interação (CLI / Web)
    ┌──────────▼─────────────┐
    │    Front / Web UI       │
    │    (web/)               │
    └──────────┬─────────────┘
           │ HTTP / JS
    ┌──────────▼─────────────┐
    │    Services (Python)   │
    │    (src/Services/)     │
    │  • WebService          │
    │  • MCPService          │
    │  • MachineService      │
    └──────────┬─────────────┘
           │ Internal calls / DB
    ┌──────────▼─────────────┐
    │   Repositories / DB    │
    │   (Repository/, DB/)   │
    └──────────┬─────────────┘
           │ Models
    ┌──────────▼─────────────┐
    │      Domain Models     │
    │      (models/)         │
    └────────────────────────┘
```

### Componentes principais

- `src/Services/` — implementação de serviços e orchestrators.
- `Repository/` — abstrações de persistência (MachineRepository, UserRepository).
- `models/` — classes de domínio (`Machine`, `User`, `Agent`).
- `web/` — frontend estático (HTML/CSS/JS) para operações básicas.

## Instalação

### Pré-requisitos

- Python 3.8+
- Git

### Passos rápidos

```bash
# clonar
git clone https://github.com/yourusername/mcp.git
cd mcp

# criar e ativar venv
python -m venv .venv
source .venv/bin/activate

# instalar dependências (se existir requirements)
pip install -r requirements.txt || true
```

## Configuração

Alguns serviços leem variáveis de ambiente ou arquivos locais. Exemplos:

- `DB/` pode ser configurado para caminho local (ver `src/DB/DBConnection.py`).
- Para serviços web, edite portas e settings em `src/Services/WebService.py` quando aplicável.

Recomendação: crie um `.env` na raiz com variáveis locais (não commitar):

```env
# Exemplo
MCP_ENV=development
DB_PATH=./DB/data.sqlite
WEB_PORT=8080
```

## Uso

Executar o entrypoint principal (exemplo):

```bash
python src/index.py
```

Serviços específicos podem ter seus próprios scripts em `src/Services/`.

### Interface web

Abra `web/index.html` via servidor estático (ou rode `WebService` para servir os arquivos).

## Desenvolvimento

Estrutura resumida:

```
src/
├── Services/
│   ├── MCP/
│   ├── MachineService.py
│   └── WebService.py
├── DB/
└── index.py
models/
Repository/
web/
```

Dependências de desenvolvimento e execução estão em `requirements.txt` quando presentes.

## Contribuição

Contribuições são bem-vindas. Fluxo sugerido:

1. Fork o repositório
2. Crie branch: `git checkout -b feature/nome-da-feature`
3. Faça commits atômicos
4. Abra PR descrevendo mudanças e motivação

Inclua testes quando possível e atualize esta documentação.

## Troubleshooting

Erro comum: serviço não inicia

- Verifique portas em uso (`lsof -i :8080`).
- Verifique `DB_PATH` e permissões de escrita.

Erro de importação

- Confirme ativação do venv e instalação de dependências.

## Links úteis

- Python: https://www.python.org/
- VS Code: https://code.visualstudio.com/

## Licença

Licenciado sob MIT — veja o arquivo `LICENSE`.

---

Se quiser, adapto este `README.md` para:

1. Versão em inglês
2. Adicionar badges de CI/cobertura
3. Tornar o quickstart específico para cada serviço

Diga qual dessas opções prefere e eu aplico a seguir.
---

Se quiser, faço uma versão em inglês, adiciono badges extras (CI/cobertura) ou adapto o conteúdo para publicar como release/README mais curto para o GitHub.
