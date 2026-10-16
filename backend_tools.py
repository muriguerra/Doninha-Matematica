"""
backend_tools.py - Prompt do Tutor e ferramentas compartilhadas
================================================================
Separado do backend.py para que tanto o pipeline legado quanto o
grafo LangGraph (graph_agent.py) possam importar sem import circular.
"""

import os
import re
from pathlib import Path

import httpx
import sympy

from rag.retriever import buscar_contexto

system_instruction = """
You are the "Math Weasel" (Doninha Matematica), an exceptional, didactic, patient, and highly engaging math tutor.

Your mission is NOT to be a simple calculator or to solve problems mechanically. You are a guide for mathematical thinking. Your goal is to make the student understand the "why" and not just the "how".

CRITICAL RULE: YOU MUST ALWAYS SPEAK IN ENGLISH. DO NOT SPEAK IN SPANISH, PORTUGUESE, OR ANY OTHER LANGUAGE. THIS IS A STRICT SYSTEM RULE.

Guidelines:
1. Adaptable Tutoring: Be a helpful tutor. If the student asks you to solve a problem, SOLVE it completely and show the clear solution. ONLY use the Socratic method (guiding with questions instead of giving the final answer) if the student explicitly asks to learn the step-by-step process or asks for help to understand "how" to solve it themselves.
2. Contextualization: Whenever possible, show how the mathematical concept applies in the real world to spark curiosity.
3. Embracing Errors: When the student makes a mistake, don't just correct it. Show that mistakes are a fundamental part of learning. Point out where the flaw in reasoning occurred and encourage them to try again.
4. Clarity and Didactics: Explain theoretical concepts step by step, using simple analogies before moving to mathematical rigor.
5. Formatting: You MUST use rigorous LaTeX formatting for math. IMPORTANT: Use `$` for inline math (e.g., $x^2$) and `$$` for block math (e.g., $$\\\\lim_{x \\\\to a} f(x)$$). DO NOT use `\\\\(` or `\\\\[`.
6. Clarifying Doubts: If the student asks "how it works", explain deeply. Always prompt the student at the end: "Is this clear so far? What part would you like to explore more?"
"""


def resolver_expressao_matematica(expressao: str) -> str:
    """Resolve expressões matemáticas exatas ou equações e retorna o resultado.
    Exemplos de input aceitos: '2 * 3 + 5', '5 ^ 4', '2x + 4 = 10'
    """
    try:
        expressao = expressao.replace('^', '**')
        expressao = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expressao)

        if '=' in expressao:
            lado_esq, lado_dir = expressao.split('=', 1)
            eq = sympy.Eq(sympy.sympify(lado_esq), sympy.sympify(lado_dir))

            variaveis = eq.free_symbols
            if not variaveis:
                return str(sympy.sympify(lado_esq).evalf() == sympy.sympify(lado_dir).evalf())

            var = list(variaveis)[0]
            solucao = sympy.solve(eq, var)
            print(f"\n[FERRAMENTA EXECUTADA]: Equação '{expressao}'. Resultado: {var} = {solucao}")
            return f"{var} = {solucao}"

        resultado = sympy.sympify(expressao).evalf()
        print(f"\n[FERRAMENTA EXECUTADA]: '{expressao}'. Resultado: {resultado}")
        return str(resultado)
    except Exception as e:
        print(f"\n[ERRO NA FERRAMENTA]: '{expressao}'. Erro: {e}")
        return f"Erro ao calcular: {e}"


def pesquisar_nos_livros(termo_de_busca: str) -> str:
    """Busca nos livros didaticos do aluno por definicoes, teoremas e conceitos."""
    print(f"  [FERRAMENTA] Buscando nos livros por '{termo_de_busca}'...")
    resultado = buscar_contexto(termo_de_busca)
    if not resultado:
        print("  [FERRAMENTA] Nenhum conteudo encontrado nos livros.")
        return ""
    preview = resultado.replace('\n', ' ')[:80] + "..."
    print(f"  [FERRAMENTA] Encontrado: {preview}")
    return resultado


# ─── Wolfram|Alpha LLM API ───────────────────────────────────────────────────

WOLFRAM_URL = "https://www.wolframalpha.com/api/v1/llm-api"

# Linhas que so poluem o contexto do LLM (imagens, links, codigo Wolfram)
_WOLFRAM_RUIDO = ("image:", "Wolfram Language code:", "Wolfram|Alpha website result",
                  "https://", "To use as", "(order n approximation")


def _ler_env(chave: str) -> str:
    """Le uma variavel do ambiente ou do .env (sem depender de python-dotenv)."""
    if os.getenv(chave):
        return os.environ[chave]
    env = Path(__file__).parent / ".env"
    if env.exists():
        for linha in env.read_text(encoding="utf-8-sig").splitlines():
            k, _, v = linha.partition("=")
            if k.strip() == chave:
                return v.strip().strip('"').strip("'")
    return ""


WOLFRAM_APP_ID = _ler_env("WOLFRAM_APP_ID")


def consultar_wolfram(consulta: str, max_chars: int = 2500) -> str:
    """Consulta a Wolfram|Alpha LLM API e devolve texto limpo (ou "" se falhar)."""
    if not WOLFRAM_APP_ID:
        print("  [WOLFRAM] WOLFRAM_APP_ID ausente no .env. Ignorando.")
        return ""
    print(f"  [WOLFRAM] Consultando: '{consulta}'")
    try:
        resp = httpx.get(
            WOLFRAM_URL,
            params={"input": consulta, "appid": WOLFRAM_APP_ID, "maxchars": 4000},
            timeout=20,
        )
    except httpx.HTTPError as e:
        print(f"  [WOLFRAM] Erro de rede: {e}")
        return ""

    if resp.status_code != 200:
        print(f"  [WOLFRAM] HTTP {resp.status_code}: {resp.text[:80]}")
        return ""

    linhas = [l for l in resp.text.splitlines()
              if not any(l.strip().startswith(r) or r in l for r in _WOLFRAM_RUIDO)]
    texto = re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()[:max_chars]
    print(f"  [WOLFRAM] OK ({len(texto)} chars)")
    return texto
