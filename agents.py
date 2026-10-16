"""
agents.py - Pipeline Multi-Agente para Doninha Matematica
=========================================================
3 agentes especializados que trabalham em sequencia:
  1. Router   -> Classifica a intencao do usuario
  2. Evaluator -> Filtra relevancia do conteudo das ferramentas
  3. Tutor    -> (vive no backend.py, faz o streaming final)
"""

import json
import re
import ollama

# ═══════════════════════════════════════════════════════════════════════════════
# AGENTE 1 — ROUTER (Roteador)
# ═══════════════════════════════════════════════════════════════════════════════

ROUTER_PROMPT = """You are a classification assistant. Your ONLY job is to analyze the user's message and decide what tools are needed.

Classify the message into ONE of these categories:
- "chat_only": The user is greeting, making small talk, or asking something that does NOT require math calculations or textbook lookups.
- "needs_rag": The user is asking about math theory, definitions, theorems, rules, or concepts that could be found in textbooks.
- "needs_calc": The user wants SIMPLE arithmetic or a simple algebraic equation solved (like "2x+3=7" or "15% of 240").
- "needs_advanced": The user wants an ADVANCED computation: integrals, derivatives, limits, series, infinite sums, differential equations, matrices, eigenvalues, or systems of equations.
- "needs_both": The user needs both a textbook lookup AND a simple calculation.

RULES:
- If the user asks "what is X" or "explain X" about a math concept, classify as "needs_rag".
- If the user gives a simple expression to solve (like "2x+3=7"), classify as "needs_calc".
- If the user asks to integrate, differentiate, find a limit, solve an ODE, etc., classify as "needs_advanced".
- If the user just says "hello" or "thanks", classify as "chat_only".
- For "needs_rag", extract the best search term in "search_term".
- For "needs_calc", extract the math expression in "calc_expression".
- For "needs_advanced", write a short English Wolfram Alpha query in "wolfram_query".

You MUST respond with ONLY valid JSON. No extra text. No explanation.

Example outputs:
{"action": "chat_only"}
{"action": "needs_rag", "search_term": "definition of derivative"}
{"action": "needs_calc", "calc_expression": "2*x + 3 = 7"}
{"action": "needs_advanced", "wolfram_query": "integrate x^2 sin(x) dx"}
{"action": "needs_both", "search_term": "chain rule", "calc_expression": "3*x^2 + 2*x"}
"""


def _parse_json_safe(text: str) -> dict:
    """Tenta extrair JSON de uma resposta que pode conter texto extra."""
    # Tenta parsear direto
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Tenta encontrar JSON dentro do texto (modelo pode enrolar)
    # Modelos pequenos as vezes emitem 1 JSON por intencao, ex:
    #   {"action": "needs_rag", ...}{"action": "needs_calc", ...}  -> junta em needs_both
    objetos = []
    for bloco in re.findall(r'\{[^{}]*\}', text):
        try:
            objetos.append(json.loads(bloco))
        except json.JSONDecodeError:
            pass
    if len(objetos) > 1:
        acoes = {o.get("action") for o in objetos}
        if {"needs_rag", "needs_calc"} <= acoes or "needs_both" in acoes:
            merged = {k: v for o in objetos for k, v in o.items()}
            merged["action"] = "needs_both"
            return merged
    if objetos:
        return objetos[0]

    # Fallback: tenta detectar a intencao pelo conteudo
    text_lower = text.lower()
    if "needs_advanced" in text_lower:
        return {"action": "needs_advanced"}
    if "needs_rag" in text_lower:
        return {"action": "needs_rag", "search_term": "math concept"}
    if "needs_calc" in text_lower:
        return {"action": "needs_calc", "calc_expression": ""}
    if "needs_both" in text_lower:
        return {"action": "needs_both", "search_term": "math concept", "calc_expression": ""}

    return {"action": "chat_only"}


def router_agent(user_message: str, model: str) -> dict:
    """
    Agente 1: Analisa a mensagem do usuario e classifica a intencao.

    Retorna dict com:
      - action: "chat_only" | "needs_rag" | "needs_calc" | "needs_advanced" | "needs_both"
      - search_term: str (se needs_rag ou needs_both)
      - calc_expression: str (se needs_calc ou needs_both)
      - wolfram_query: str (se needs_advanced)
    """
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": user_message},
            ],
            stream=False,
            options={"temperature": 0.1, "num_predict": 150},  # Rapido e determinístico
        )

        # Extrai o conteudo da resposta
        if isinstance(response, dict):
            raw = response.get("message", {}).get("content", "")
        else:
            raw = getattr(getattr(response, "message", None), "content", "")

        print(f"  [ROUTER] Resposta bruta: {raw.strip()}")
        result = _parse_json_safe(raw)
        print(f"  [ROUTER] Decisao: {result}")
        return result

    except Exception as e:
        print(f"  [ROUTER] Erro: {e}. Fallback para chat_only.")
        return {"action": "chat_only"}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTE 2 — EVALUATOR (Avaliador de Relevancia)
# ═══════════════════════════════════════════════════════════════════════════════

EVALUATOR_PROMPT = """You are a relevance filter. Your ONLY job is to check if the provided context is useful for answering the user's question.

You will receive:
1. The user's question
2. Context retrieved from tools (textbook excerpts or calculation results)

Decide:
- If the context is relevant and helps answer the question, set "relevant" to true and copy the useful parts into "useful_context".
- If the context is irrelevant, off-topic, or garbage, set "relevant" to false.

You MUST respond with ONLY valid JSON. No extra text.

Example outputs:
{"relevant": true, "useful_context": "The derivative of f(x) is defined as the limit..."}
{"relevant": false}
"""


def evaluator_agent(user_question: str, tool_context: str, model: str) -> dict:
    """
    Agente 2: Avalia se o conteudo retornado pelas ferramentas e relevante.

    Retorna dict com:
      - relevant: bool
      - useful_context: str (somente se relevant=True)
    """
    try:
        eval_input = f"USER QUESTION: {user_question}\n\nCONTEXT FROM TOOLS:\n{tool_context}"

        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": EVALUATOR_PROMPT},
                {"role": "user", "content": eval_input},
            ],
            stream=False,
            options={"temperature": 0.1, "num_predict": 500},
        )

        if isinstance(response, dict):
            raw = response.get("message", {}).get("content", "")
        else:
            raw = getattr(getattr(response, "message", None), "content", "")

        preview = raw.strip().replace('\n', ' ')
        if len(preview) > 100:
            preview = preview[:100] + "..."
        print(f"  [EVALUATOR] Resposta bruta: {preview}")

        result = _parse_json_safe(raw)

        # Se o parser falhou em achar "relevant", assume relevante se tem contexto
        if "relevant" not in result:
            result = {"relevant": bool(tool_context), "useful_context": tool_context}

        print(f"  [EVALUATOR] Relevante: {result.get('relevant', False)}")
        return result

    except Exception as e:
        print(f"  [EVALUATOR] Erro: {e}. Assumindo contexto relevante.")
        return {"relevant": True, "useful_context": tool_context}
