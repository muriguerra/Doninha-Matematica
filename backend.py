import os
import uuid
import json
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import ollama

from sqlalchemy.orm import Session
from sqlalchemy import text
from db.database import SessionLocal, engine
from db import models
from agents import router_agent, evaluator_agent
from backend_tools import system_instruction, resolver_expressao_matematica, pesquisar_nos_livros

# Liga/desliga o pipeline LangGraph (graph_agent.py). USE_LANGGRAPH=0 volta ao pipeline manual.
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "1") != "0"
if USE_LANGGRAPH:
    from graph_agent import stream_events as graph_stream_events

# Cria as tabelas no banco de dados se elas não existirem
models.Base.metadata.create_all(bind=engine)

# Migração simples automática: adiciona a coluna device_id caso não exista
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN device_id VARCHAR DEFAULT 'unknown'"))
        conn.commit()
except Exception:
    pass # Coluna já existe

# Inicializa nossa API
app = FastAPI(title="Doninha Matemática Tutor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependência para pegar a sessão do banco de dados em cada request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── Helper para extrair campos de chunks do Ollama ──────────────────────────
# O ollama-python pode retornar dicts (versões antigas) ou objetos tipados (v0.2+)
# Esta função trata os dois casos.

def _get(obj, *keys, default=None):
    """Acesso seguro a dict ou objeto tipado."""
    for key in keys:
        if obj is None:
            return default
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            obj = getattr(obj, key, None)
    return obj if obj is not None else default

# ─────────────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    session_id: str | None = None
    mensagem: str
    model: str = "llama3.2"


# ─── Endpoints de suporte ────────────────────────────────────────────────────

@app.get("/models")
def get_available_models():
    """Lista os modelos disponíveis no Ollama instalado localmente."""
    try:
        result = ollama.list()
        # Suporte para dict e objeto tipado
        models_list = _get(result, 'models', default=[])
        names = []
        for m in models_list:
            name = _get(m, 'name', default='') or _get(m, 'model', default='')
            if name:
                names.append(name)
        return names if names else ["llama3.2"]
    except Exception as e:
        print(f"[AVISO]: Não foi possível listar modelos Ollama: {e}")
        return ["llama3.2"]


@app.get("/sessions")
def get_sessions(device_id: str = Header("unknown"), db: Session = Depends(get_db)):
    """Lista todas as sessões de chat, da mais recente para a mais antiga."""
    query = db.query(models.ChatSession)
    if device_id != "unknown":
        query = query.filter(models.ChatSession.device_id == device_id)
    sessions = query.order_by(models.ChatSession.created_at.desc()).all()
    result = []
    for s in sessions:
        # Usa a primeira mensagem do usuário como título da sessão
        first_msg = (
            db.query(models.Message)
            .filter(models.Message.session_id == s.id, models.Message.role == "user")
            .order_by(models.Message.id)
            .first()
        )
        if first_msg:
            title = first_msg.content[:60] + ("..." if len(first_msg.content) > 60 else "")
        else:
            title = "Sessão vazia"

        result.append({
            "id": s.id,
            "created_at": s.created_at.isoformat() if s.created_at else "",
            "title": title,
        })
    return result


@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """Retorna as mensagens de usuário e assistente de uma sessão específica."""
    sessao = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    messages = (
        db.query(models.Message)
        .filter(
            models.Message.session_id == session_id,
            models.Message.role.in_(["user", "assistant"])
        )
        .order_by(models.Message.id)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in messages]


# ─── Endpoint principal de chat (SSE Streaming) ──────────────────────────────

@app.post("/chat")
def chat_endpoint(request: ChatRequest, device_id: str = Header("unknown"), db: Session = Depends(get_db)):
    session_id = request.session_id
    current_model = request.model

    # 1. Verifica/Cria a Sessão no Banco de Dados
    if not session_id:
        session_id = str(uuid.uuid4())
        nova_sessao = models.ChatSession(id=session_id, device_id=device_id)
        db.add(nova_sessao)
        msg_system = models.Message(session_id=session_id, role="system", content=system_instruction)
        db.add(msg_system)
        db.commit()
        print(f"Nova sessão DB criada: {session_id} (Modelo: {current_model})")
    else:
        sessao_existe = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
        if not sessao_existe:
            raise HTTPException(status_code=404, detail="Sessão não encontrada no banco de dados.")

    # 2. Salva a nova mensagem do Usuário
    msg_user = models.Message(session_id=session_id, role="user", content=request.mensagem)
    db.add(msg_user)
    db.commit()

    # Log no terminal: Mensagem do usuário
    user_preview = request.mensagem.replace('\n', ' ')
    if len(user_preview) > 60: user_preview = user_preview[:60] + "..."
    print(f"\n[USUÁRIO] {user_preview}")

    # 3. Monta o histórico completo da sessão
    mensagens_bd = (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id)
        .order_by(models.Message.id)
        .all()
    )
    historico = [{"role": m.role, "content": m.content} for m in mensagens_bd]

    # 4. Generator SSE — Pipeline Multi-Agente
    def generate():
        db_gen = SessionLocal()
        try:
            print(f"\n{'='*60}")
            print(f"[PIPELINE] Iniciando pipeline multi-agente. Modelo: {current_model}"
                  f" | Motor: {'LangGraph' if USE_LANGGRAPH else 'manual'}")
            print(f"{'='*60}")

            # ════════════════════════════════════════════════════════════
            # MOTOR LANGGRAPH (graph_agent.py) — o grafo emite status e tokens
            # ════════════════════════════════════════════════════════════
            if USE_LANGGRAPH:
                accumulated_content = ""
                for evento in graph_stream_events(request.mensagem, historico, current_model):
                    if evento.get("type") == "chunk":
                        accumulated_content += evento["content"]
                    yield f"data: {json.dumps(evento)}\n\n"

                db_gen.add(models.Message(session_id=session_id, role="assistant", content=accumulated_content))
                db_gen.commit()
                print(f"\n[DONINHA] {accumulated_content.replace(chr(10), ' ')[:80]}...")
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'modelo': current_model})}\n\n"
                return

            # ════════════ MOTOR MANUAL (legado, mantido para comparacao) ════════════

            # ════════════════════════════════════════════════════════════
            # AGENTE 1: ROUTER — Classifica a intencao do usuario
            # ════════════════════════════════════════════════════════════
            ultima_msg = request.mensagem
            print(f"\n[AGENTE 1 - ROUTER] Analisando: '{ultima_msg[:50]}...'")
            yield f"data: {json.dumps({'type': 'status', 'message': 'Analyzing your question...'})}\n\n"

            decisao = router_agent(ultima_msg, current_model)
            action = decisao.get("action", "chat_only")

            # ════════════════════════════════════════════════════════════
            # EXECUCAO DE FERRAMENTAS (baseado na decisao do Router)
            # ════════════════════════════════════════════════════════════
            contexto_extra = ""
            tool_outputs = []

            if action in ("needs_rag", "needs_both"):
                search_term = decisao.get("search_term", ultima_msg)
                print(f"\n[FERRAMENTAS] Router pediu RAG. Termo: '{search_term}'")
                yield f"data: {json.dumps({'type': 'status', 'message': 'Searching textbooks...'})}\n\n"
                rag_result = pesquisar_nos_livros(search_term)
                if rag_result:
                    tool_outputs.append(f"[TEXTBOOK EXCERPTS]\n{rag_result}")

            if action in ("needs_calc", "needs_both"):
                calc_expr = decisao.get("calc_expression", "")
                if calc_expr:
                    print(f"\n[FERRAMENTAS] Router pediu calculo. Expressao: '{calc_expr}'")
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Calculating...'})}\n\n"
                    calc_result = resolver_expressao_matematica(calc_expr)
                    tool_outputs.append(f"[CALCULATION RESULT]\n{calc_expr} => {calc_result}")

            # ════════════════════════════════════════════════════════════
            # AGENTE 2: EVALUATOR — Filtra relevancia (so se usou tools)
            # ════════════════════════════════════════════════════════════
            if tool_outputs:
                raw_context = "\n\n".join(tool_outputs)
                print(f"\n[AGENTE 2 - EVALUATOR] Avaliando relevancia do contexto...")
                yield f"data: {json.dumps({'type': 'status', 'message': 'Evaluating relevance...'})}\n\n"

                avaliacao = evaluator_agent(ultima_msg, raw_context, current_model)

                if avaliacao.get("relevant", False):
                    contexto_extra = avaliacao.get("useful_context", raw_context)
                    print(f"  [EVALUATOR] Contexto APROVADO ({len(contexto_extra)} chars)")
                else:
                    print(f"  [EVALUATOR] Contexto REJEITADO (irrelevante)")
                    contexto_extra = ""
            else:
                if action == "chat_only":
                    print(f"\n[PIPELINE] Modo conversa. Nenhuma ferramenta necessaria.")

            # ════════════════════════════════════════════════════════════
            # AGENTE 3: TUTOR (DONINHA) — Resposta final com streaming
            # ════════════════════════════════════════════════════════════
            print(f"\n[AGENTE 3 - TUTOR] Gerando resposta final...")

            historico_enviado = list(historico)

            # Injeta contexto avaliado no system prompt (se houver)
            if contexto_extra and historico_enviado and historico_enviado[0]["role"] == "system":
                prompt_original = historico_enviado[0]["content"]
                prompt_enriquecido = (
                    f"{prompt_original}\n\n"
                    f"[VERIFIED REFERENCE MATERIAL]\n"
                    f"The following information was retrieved from tools and verified as relevant. "
                    f"Use it to support your answer:\n\n"
                    f"{contexto_extra}\n\n"
                    f"[END OF REFERENCE MATERIAL]"
                )
                historico_enviado[0] = {"role": "system", "content": prompt_enriquecido}

            # Stream da resposta do Tutor
            stream = ollama.chat(
                model=current_model,
                messages=historico_enviado,
                stream=True,
            )

            accumulated_content = ""
            for chunk in stream:
                msg = _get(chunk, 'message', default={})
                content = _get(msg, 'content', default='') or ''
                if content:
                    accumulated_content += content
                    yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"

            # Salva a resposta final no banco
            db_gen.add(models.Message(session_id=session_id, role="assistant", content=accumulated_content))
            db_gen.commit()

            ast_preview = accumulated_content.replace('\n', ' ')
            if len(ast_preview) > 80: ast_preview = ast_preview[:80] + "..."
            print(f"\n[DONINHA] {ast_preview}")
            print(f"{'='*60}\n")

            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'modelo': current_model})}\n\n"

        except Exception as e:
            print(f"[ERRO NO PIPELINE]: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            db_gen.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # Desabilita buffering no Nginx se usado
        },
    )

# Serve o frontend estaticamente para facilitar o acesso público via ngrok
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
