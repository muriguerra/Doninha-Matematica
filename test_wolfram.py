"""
test_wolfram.py - Teste cru da Wolfram|Alpha LLM API
====================================================
Le o WOLFRAM_APP_ID do arquivo .env e faz consultas diretas na API,
mostrando status HTTP, tempo de resposta e o texto bruto retornado.

Uso:
    python test_wolfram.py                          # roda a bateria de testes
    python test_wolfram.py "integrate x^2 sin(x)"   # consulta unica
    python test_wolfram.py -i                       # modo interativo

Docs: https://products.wolframalpha.com/llm-api/documentation
"""

import os
import sys
import time
from pathlib import Path

import httpx

API_URL = "https://www.wolframalpha.com/api/v1/llm-api"

# Consultas que o SymPy sofre (ou nao faz) e o Wolfram resolve bem
TESTES = [
    "integrate x^2 sin(x) dx",
    "solve y'' + 4y = sin(2x)",
    "limit (1 + 1/n)^n as n -> infinity",
    "derivative of x^x",
    "sum 1/n^2 from n=1 to infinity",
    "eigenvalues {{2,1},{1,3}}",
    "taylor series of e^x cos(x) at x=0 to order 5",
    "what is the chain rule",  # pergunta conceitual: ver como a API reage
]


def carregar_app_id() -> str:
    """Le WOLFRAM_APP_ID do ambiente ou do .env (sem depender de python-dotenv)."""
    if os.getenv("WOLFRAM_APP_ID"):
        return os.environ["WOLFRAM_APP_ID"]
    env = Path(__file__).parent / ".env"
    if env.exists():
        for linha in env.read_text(encoding="utf-8-sig").splitlines():
            chave, _, valor = linha.partition("=")
            if chave.strip() == "WOLFRAM_APP_ID":
                return valor.strip().strip('"').strip("'")
    sys.exit("ERRO: defina WOLFRAM_APP_ID no .env")


def consultar(pergunta: str, app_id: str, max_chars: int = 6800) -> tuple[int, str, float]:
    """Faz a chamada crua. Retorna (status_http, texto, segundos)."""
    params = {"input": pergunta, "appid": app_id, "maxchars": max_chars}
    inicio = time.perf_counter()
    resp = httpx.get(API_URL, params=params, timeout=30)
    return resp.status_code, resp.text, time.perf_counter() - inicio


def mostrar(pergunta: str, app_id: str) -> bool:
    print("\n" + "=" * 70)
    print(f">>> {pergunta}")
    print("=" * 70)
    try:
        status, texto, seg = consultar(pergunta, app_id)
    except httpx.HTTPError as e:
        print(f"[ERRO DE REDE] {e}")
        return False

    print(f"[HTTP {status}] {seg:.2f}s | {len(texto)} chars\n")
    print(texto)

    # Codigos documentados da LLM API
    if status == 401:
        print("\n⚠️  401: App ID invalido. Formato esperado: XXXXXX-XXXXXXXXXX "
              "(confira no portal; App IDs novos podem levar alguns minutos para ativar).")
    elif status == 403:
        print("\n⚠️  403: App ID invalido, ou nao habilitado para a LLM API.")
    elif status == 501:
        print("\n⚠️  501: o Wolfram nao entendeu a consulta (tente reformular em ingles).")
    elif status == 400:
        print("\n⚠️  400: parametro 'input' ausente ou invalido.")
    return status == 200


def main():
    app_id = carregar_app_id()
    print(f"App ID carregado: {app_id[:3]}***{app_id[-2:]}")

    args = sys.argv[1:]
    if args and args[0] == "-i":
        print("Modo interativo. Linha vazia para sair.")
        while (q := input("\nwolfram> ").strip()):
            mostrar(q, app_id)
        return

    consultas = [" ".join(args)] if args else TESTES
    resultados = [(q, mostrar(q, app_id)) for q in consultas]

    if len(resultados) > 1:
        print("\n" + "=" * 70 + "\nRESUMO")
        for q, ok in resultados:
            print(f"  {'✅' if ok else '❌'} {q}")


if __name__ == "__main__":
    main()
