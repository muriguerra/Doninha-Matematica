import os
import warnings

# Oculta o aviso chato do langchain_community sobre a biblioteca de PDF
warnings.filterwarnings("ignore", category=DeprecationWarning)
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage.file_system import LocalFileStore
from langchain_classic.storage._lc_store import create_kv_docstore

# Caminhos relativos à raiz do projeto
DATA_PATH = "data"
CHROMA_PATH = "db/chroma"
DOCSTORE_PATH = "db/docstore"

def main():
    print("[INFO] Carregando documentos em PDF da pasta 'data/'...")
    
    if not os.path.exists(DATA_PATH) or not os.listdir(DATA_PATH):
        print(f"[AVISO] Nenhum arquivo encontrado. Coloque seus PDFs na pasta: {os.path.abspath(DATA_PATH)}")
        return

    loader = PyPDFDirectoryLoader(DATA_PATH)
    documents = loader.load()
    
    if not documents:
        print("[AVISO] Não foi possível extrair texto dos PDFs.")
        return

    print(f"[OK] {len(documents)} páginas carregadas. Estruturando em formato Parent-Child (Pai-Filho)...")
    
    # Textos pais (maiores, contexto amplo)
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        length_function=len
    )
    
    # Textos filhos (menores, foco exato para a busca semântica)
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        length_function=len
    )

    print("[INFO] Carregando modelo de embeddings all-MiniLM-L6-v2...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Cria a base de vetores (Child) e a base de documentos puros (Parent)
    vectorstore = Chroma(
        collection_name="parent_child_splits",
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH
    )
    
    fs = LocalFileStore(DOCSTORE_PATH)
    store = create_kv_docstore(fs)
    
    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=store,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
    )
    
    print("[INFO] Processando documentos em lotes para evitar limite de batch do ChromaDB...")
    
    # Processa em lotes de 100 documentos (páginas) por vez
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        print(f"       -> Processando lote {i//batch_size + 1}/{(len(documents)//batch_size) + 1}...")
        retriever.add_documents(batch)
    
    print("[SUCESSO] Base de conhecimento (RAG) atualizada com sucesso para Parent-Child!")

if __name__ == "__main__":
    main()
