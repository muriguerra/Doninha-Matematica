# Doninha Matemática Local Math Tutor

Este é um projeto de estudos focado na construção de uma arquitetura baseada em Inteligência Artificial para tutoria de matemática. O objetivo é simular o produto da Doninha Matemática, onde um modelo de linguagem guia o aluno socraticamente, em vez de apenas dar a resposta final.

Nesta iteração do projeto, o foco está na utilização de **Modelos Locais (SLMs/LLMs)**, garantindo privacidade total, controle da infraestrutura e isenção de limites de cota ou custos de APIs de terceiros.

## Arquitetura do Projeto

*   **Modelo de Linguagem Local:** Executado via [Ollama](https://ollama.com/), utilizando modelos eficientes (ex: `llama3.2` ou `qwen2.5-math`).
*   **Orquestrador (Backend):** Servidor RESTful construído em Python com **FastAPI**. Responsável por manter a sessão do usuário, gerenciar a Janela de Contexto (Context Window) e servir como ponte entre o aluno e o modelo.
*   **Agente Matemático (ReAct / Tool Calling):** Modelos de linguagem sofrem com alucinações matemáticas. O backend intercepta as necessidades de cálculo do modelo e delega a matemática bruta para ferramentas exatas como a biblioteca `sympy`.
*   **Frontend e Banco de Dados:** (Em desenvolvimento para as próximas fases do estudo).

## Instalação e Uso

### Pré-requisitos
1.  Python 3.10 ou superior.
2.  [Ollama instalado](https://ollama.com/download) na sua máquina.

### Passos (Linux)
1. Instale o Ollama e baixe o modelo usado nos testes:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull qwen2.5:3b        # ou: ollama pull llama3.2
   ```
2. Crie o ambiente virtual e instale as dependências:
   ```bash
   python3 -m venv venv
   ./venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
   ./venv/bin/pip install -r requirements.txt
   ```
3. Indexe os PDFs da pasta `data/` (gera `db/chroma/` e `db/docstore/`):
   ```bash
   ./venv/bin/python rag/ingest.py
   ```
4. (Opcional) Configure `WOLFRAM_APP_ID` no `.env` para cálculos avançados.
5. Suba o backend e acesse http://127.0.0.1:8000 (Swagger em `/docs`):
   ```bash
   ./venv/bin/uvicorn backend:app --host 0.0.0.0 --port 8000
   ```

> O histórico de chats fica em `doninha.db` (SQLite, criado automaticamente).