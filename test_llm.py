import requests

def testar_api():
    print("=========================================================")
    print("🧪 TESTADOR DA API DONINHA MATEMÁTICA (Backend com Ollama)")
    print("=========================================================\n")
    
    url = "http://127.0.0.1:8000/chat"
    session_id = None
    
    print("Digite 'sair' para encerrar a conversa.\n")
    
    while True:
        mensagem = input("[Você]: ")
        if mensagem.lower() in ["sair", "exit", "quit"]:
            break
            
        payload = {
            "mensagem": mensagem,
            "model": "llama3.2"  # Você pode trocar para qwen2.5-math aqui depois!
        }
        
        # Só manda o session_id se já tivermos um
        if session_id:
            payload["session_id"] = session_id
            
        try:
            resposta = requests.post(url, json=payload)
            dados = resposta.json()
            
            # Atualiza o session_id para manter a memória!
            session_id = dados.get("session_id")
            
            print(f"\n[Tutor ({dados.get('modelo_utilizado')})]: {dados.get('resposta')}\n")
            print("-" * 50)
            
        except requests.exceptions.ConnectionError:
            print("\n❌ ERRO: Não foi possível conectar ao servidor.")
            print("Verifique se o backend está rodando com 'uvicorn backend:app --reload'")
            break

if __name__ == "__main__":
    testar_api()
