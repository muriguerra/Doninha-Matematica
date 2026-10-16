import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage.file_system import LocalFileStore
from langchain_classic.storage._lc_store import create_kv_docstore
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Este arquivo é chamado pelo backend.py que está na raiz
CHROMA_PATH = "db/chroma"
DOCSTORE_PATH = "db/docstore"

# Variáveis globais para armazenar o retriever cacheado
retriever_cache = None

def get_retriever():
    global retriever_cache
    if retriever_cache is not None:
        return retriever_cache
        
    if not os.path.exists(CHROMA_PATH) or not os.path.exists(DOCSTORE_PATH):
        return None
        
    try:
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        vectorstore = Chroma(
            collection_name="parent_child_splits",
            embedding_function=embeddings,
            persist_directory=CHROMA_PATH
        )
        
        fs = LocalFileStore(DOCSTORE_PATH)
        store = create_kv_docstore(fs)
        
        # Os splitters precisam ser passados, mesmo que apenas para leitura da estrutura
        parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000)
        child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)
        
        retriever_cache = ParentDocumentRetriever(
            vectorstore=vectorstore,
            docstore=store,
            child_splitter=child_splitter,
            parent_splitter=parent_splitter,
        )
        # Ajusta a quantidade de documentos pai a retornar
        retriever_cache.search_kwargs = {"k": 3}
        return retriever_cache
    except Exception as e:
        print(f"[RAG] Aviso: Falha ao inicializar ParentDocumentRetriever: {e}")
        return None

def buscar_contexto(pergunta: str, k: int = 3) -> str:
    """Busca os trechos mais relevantes dos seus PDFs de acordo com a pergunta do usuário."""
    retriever = get_retriever()
    if not retriever:
        return ""
        
    try:
        # Atualiza o k caso seja diferente
        retriever.search_kwargs = {"k": k}
        
        # O invoke traz os documentos pais completos correspondentes aos filhos mais similares
        resultados = retriever.invoke(pergunta)
        
        if not resultados:
            return ""
            
        # Pega o conteúdo dos PDFs e monta um mega texto
        textos = [f"- {doc.page_content}" for doc in resultados]
        contexto_unido = "\n\n".join(textos)
        
        return contexto_unido
    except Exception as e:
        print(f"[RAG] Erro ao buscar contexto no banco de dados: {e}")
        return ""
