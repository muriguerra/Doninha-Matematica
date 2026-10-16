"""
graph_agent.py - Pipeline Multi-Agente da Doninha usando LangGraph
==================================================================
Mesmo pipeline do backend (Router -> Ferramentas -> Evaluator -> Tutor),
mas agora modelado como um GRAFO DE ESTADOS (StateGraph).

O que ganhamos em relacao ao pipeline manual (if/else no backend.py):
  1. ESTADO explicito e tipado (DoninhaState) que flui entre os nos.
  2. ARESTAS CONDICIONAIS: o roteamento vira dado, nao codigo espalhado.
  3. PARALELISMO: "needs_both" dispara RAG e Calculadora ao mesmo tempo.
  4. CICLOS: se o Evaluator rejeitar o RAG, o grafo reescreve a busca e
     tenta de novo (algo que um pipeline linear nao faz de forma limpa).
  5. STREAMING customizado: status + tokens saem via get_stream_writer().
  6. FALLBACK entre ferramentas: SymPy (local) -> Wolfram|Alpha (nuvem)
     quando o SymPy falha; contas avancadas vao direto ao Wolfram.

Teste rapido pelo terminal:
    python graph_agent.py                       # pergunta padrao
    python graph_agent.py "what is a derivative" qwen2.5
    python graph_agent.py --mermaid             # imprime o diagrama do grafo
"""

from typing import Literal, TypedDict

import ollama
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from agents import _parse_json_safe, evaluator_agent, router_agent
from backend_tools import WOLFRAM_APP_ID

MAX_RAG_RETRIES = 1  # Quantas vezes o grafo pode reescrever a busca no RAG


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ESTADO — a "memoria de trabalho" compartilhada por todos os nos
# ═══════════════════════════════════════════════════════════════════════════════
# Cada no recebe o estado inteiro e devolve APENAS as chaves que quer alterar.
# O LangGraph faz o merge. Por isso rag_result e calc_result sao chaves
# separadas: os dois nos rodam em paralelo e cada um escreve na sua chave
# (se escrevessem na mesma chave sem um "reducer", daria conflito).

class DoninhaState(TypedDict, total=False):
    # Entrada
    user_message: str
    history: list[dict]          # historico completo (system + user + assistant)
    model: str

    # Saida do Router
    action: str                  # chat_only | needs_rag | needs_calc | needs_both
    search_term: str
    calc_expression: str
    wolfram_query: str

    # Saida das ferramentas
    rag_result: str
    calc_result: str
    calc_failed: bool
    wolfram_result: str
    rag_retries: int

    # Saida do Evaluator
    rag_relevant: bool
    verified_context: str

    # Saida do Tutor
    final_answer: str


def _status(message: str) -> None:
    """Envia um evento de status para quem estiver fazendo stream do grafo."""
    get_stream_writer()({"type": "status", "message": message})


# ═══════════════════════════════════════════════════════════════════════════════
# 2. NOS — cada no e uma funcao pura: (estado) -> atualizacao parcial do estado
# ═══════════════════════════════════════════════════════════════════════════════

def router_node(state: DoninhaState) -> dict:
    _status("Analyzing your question...")
    decisao = router_agent(state["user_message"], state["model"])
    return {
        "action": decisao.get("action", "chat_only"),
        "search_term": decisao.get("search_term") or state["user_message"],
        "calc_expression": decisao.get("calc_expression", ""),
        "wolfram_query": decisao.get("wolfram_query") or state["user_message"],
        "rag_retries": 0,
    }


def rag_node(state: DoninhaState) -> dict:
    # Import tardio: evita carregar ChromaDB/embeddings so para desenhar o grafo
    from rag.retriever import buscar_contexto

    _status("Searching textbooks...")
    termo = state["search_term"]
    print(f"  [RAG] Buscando: '{termo}'")
    return {"rag_result": buscar_contexto(termo) or ""}


def calc_node(state: DoninhaState) -> dict:
    from backend_tools import resolver_expressao_matematica

    expr = state.get("calc_expression", "")
    if not expr:
        print("  [CALC] Router nao extraiu expressao -> fallback")
        return {"calc_result": "", "calc_failed": True}
    _status("Calculating...")
    resultado = resolver_expressao_matematica(expr)
    if resultado.startswith("Erro"):
        print("  [CALC] SymPy falhou -> fallback")
        return {"calc_result": "", "calc_failed": True}
    return {"calc_result": f"{expr} => {resultado}", "calc_failed": False}


def wolfram_node(state: DoninhaState) -> dict:
    from backend_tools import consultar_wolfram

    _status("Consulting Wolfram|Alpha...")
    # Se veio do fallback do SymPy, a expressao original e a melhor consulta
    consulta = (state.get("calc_expression") if state.get("calc_failed") else None) \
        or state.get("wolfram_query") or state["user_message"]
    return {"wolfram_result": consultar_wolfram(consulta)}


def evaluator_node(state: DoninhaState) -> dict:
    """Avalia RAG e calculo. O calculo (SymPy) e deterministico: sempre confiavel."""
    rag = state.get("rag_result", "")
    calc = state.get("calc_result", "")

    partes = []
    rag_relevant = True
    if rag:
        _status("Evaluating relevance...")
        avaliacao = evaluator_agent(state["user_message"], rag, state["model"])
        rag_relevant = bool(avaliacao.get("relevant", False))
        if rag_relevant:
            partes.append(f"[TEXTBOOK EXCERPTS]\n{avaliacao.get('useful_context') or rag}")
    elif state.get("action") in ("needs_rag", "needs_both"):
        rag_relevant = False  # pediu RAG e nao veio nada

    if calc:
        partes.append(f"[CALCULATION RESULT (SymPy)]\n{calc}")

    # Wolfram e uma fonte computacional confiavel: entra direto, sem passar pelo LLM
    wolfram = state.get("wolfram_result", "")
    if wolfram:
        partes.append(
            "[COMPUTATION RESULT (Wolfram|Alpha) - plain text notation, "
            f"convert to LaTeX when presenting]\n{wolfram}"
        )

    return {"rag_relevant": rag_relevant, "verified_context": "\n\n".join(partes)}


REWRITE_PROMPT = """You rewrite search queries for a calculus textbook search engine.
Given the user's question and a query that returned irrelevant results, produce a
better, more specific query using standard textbook terminology (in English).
Respond ONLY with JSON: {"search_term": "..."}"""


def rewrite_query_node(state: DoninhaState) -> dict:
    _status("Refining textbook search...")
    resp = ollama.chat(
        model=state["model"],
        messages=[
            {"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": (
                f"USER QUESTION: {state['user_message']}\n"
                f"FAILED QUERY: {state['search_term']}"
            )},
        ],
        options={"temperature": 0.3, "num_predict": 60},
    )
    novo = _parse_json_safe(resp.message.content).get("search_term") or state["user_message"]
    print(f"  [REWRITE] '{state['search_term']}' -> '{novo}'")
    return {"search_term": novo, "rag_retries": state.get("rag_retries", 0) + 1}


def tutor_node(state: DoninhaState) -> dict:
    writer = get_stream_writer()
    mensagens = list(state["history"])
    contexto = state.get("verified_context", "")

    if contexto and mensagens and mensagens[0]["role"] == "system":
        mensagens[0] = {
            "role": "system",
            "content": (
                f"{mensagens[0]['content']}\n\n[VERIFIED REFERENCE MATERIAL]\n"
                f"The following information was retrieved from tools and verified as relevant. "
                f"Use it to support your answer:\n\n{contexto}\n\n[END OF REFERENCE MATERIAL]"
            ),
        }

    # Modelos pequenos "esquecem" o contexto que fica no topo do system prompt
    # e refazem a conta sozinhos (errando). Repetimos o resultado computado
    # colado na ultima mensagem do usuario (efeito de recencia).
    # So altera a copia enviada ao modelo; o historico do banco fica intacto.
    computado = "\n\n".join(
        p for p in contexto.split("\n\n[") if "RESULT" in p.split("]")[0]
    ) if contexto else ""
    if computado and mensagens and mensagens[-1]["role"] == "user":
        mensagens[-1] = {
            "role": "user",
            "content": (
                f"{mensagens[-1]['content']}\n\n"
                f"---\n[VERIFIED COMPUTATION - computed by a symbolic math engine, it is CORRECT]\n"
                f"{computado.lstrip('[')}\n---\n"
                "Your explanation MUST arrive at exactly this result. Explain the steps that lead to it. "
                "If your own derivation disagrees, your derivation has an error: fix it. "
                "Write all math in LaTeX using $...$ and $$...$$."
            ),
        }

    resposta = ""
    for chunk in ollama.chat(model=state["model"], messages=mensagens, stream=True):
        token = chunk.message.content or ""
        if token:
            resposta += token
            writer({"type": "chunk", "content": token})  # token vai direto pro SSE
    return {"final_answer": resposta}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ARESTAS CONDICIONAIS — funcoes que leem o estado e decidem o proximo no
# ═══════════════════════════════════════════════════════════════════════════════

def route_after_router(state: DoninhaState) -> list[str]:
    """Retornar uma LISTA de nos = executar todos em paralelo (fan-out)."""
    return {
        "needs_rag": ["rag_search"],
        "needs_calc": ["calculator"],
        "needs_advanced": ["wolfram"] if WOLFRAM_APP_ID else ["calculator"],
        "needs_both": ["rag_search", "calculator"],
    }.get(state.get("action"), ["tutor"])


def route_after_calculator(state: DoninhaState) -> Literal["wolfram", "evaluator"]:
    """FALLBACK: SymPy falhou e temos Wolfram configurado -> tenta na nuvem."""
    if state.get("calc_failed") and WOLFRAM_APP_ID:
        return "wolfram"
    return "evaluator"


def route_after_evaluator(state: DoninhaState) -> Literal["rewrite_query", "tutor"]:
    """O CICLO: RAG irrelevante + ainda tem tentativas -> reescreve e busca de novo."""
    if (
        not state.get("rag_relevant", True)
        and state.get("action") in ("needs_rag", "needs_both")
        and state.get("rag_retries", 0) < MAX_RAG_RETRIES
    ):
        return "rewrite_query"
    return "tutor"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MONTAGEM DO GRAFO
# ═══════════════════════════════════════════════════════════════════════════════

def build_graph():
    g = StateGraph(DoninhaState)

    g.add_node("router", router_node)
    g.add_node("rag_search", rag_node)
    g.add_node("calculator", calc_node)
    g.add_node("wolfram", wolfram_node)
    # defer=True: o evaluator so roda quando NAO houver mais nada pendente.
    # Necessario porque os ramos tem tamanhos diferentes no needs_both:
    #   rag_search -> evaluator                (1 passo)
    #   calculator -> wolfram -> evaluator     (2 passos, se o SymPy falhar)
    # Sem defer, o evaluator (e o tutor!) rodariam duas vezes.
    g.add_node("evaluator", evaluator_node, defer=True)
    g.add_node("rewrite_query", rewrite_query_node)
    g.add_node("tutor", tutor_node)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_after_router,
                            ["rag_search", "calculator", "wolfram", "tutor"])

    # Fan-in: o evaluator espera TODOS os ramos paralelos terminarem
    g.add_edge("rag_search", "evaluator")
    g.add_conditional_edges("calculator", route_after_calculator,
                            ["wolfram", "evaluator"])
    g.add_edge("wolfram", "evaluator")

    g.add_conditional_edges("evaluator", route_after_evaluator,
                            ["rewrite_query", "tutor"])
    g.add_edge("rewrite_query", "rag_search")  # <- fecha o ciclo
    g.add_edge("tutor", END)

    return g.compile()


doninha_graph = build_graph()


def stream_events(user_message: str, history: list[dict], model: str):
    """Gera eventos {'type': 'status'|'chunk', ...} — pronto para virar SSE."""
    estado_inicial: DoninhaState = {
        "user_message": user_message,
        "history": history,
        "model": model,
    }
    for evento in doninha_graph.stream(estado_inicial, stream_mode="custom"):
        yield evento


# ═══════════════════════════════════════════════════════════════════════════════
# Execucao direta pelo terminal (laboratorio de estudos)
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    if "--mermaid" in sys.argv:
        print(doninha_graph.get_graph().draw_mermaid())
        sys.exit(0)

    pergunta = sys.argv[1] if len(sys.argv) > 1 else "What is the chain rule? Also solve 2x + 3 = 7"
    modelo = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5:3b"

    from backend_tools import system_instruction
    hist = [{"role": "system", "content": system_instruction},
            {"role": "user", "content": pergunta}]

    print(f"\n>>> {pergunta}  (modelo: {modelo})\n")
    for ev in stream_events(pergunta, hist, modelo):
        if ev["type"] == "status":
            print(f"\n[status] {ev['message']}")
        else:
            print(ev["content"], end="", flush=True)
    print()
