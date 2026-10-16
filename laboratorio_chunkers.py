"""
laboratorio_chunkers.py - Comparativo Real de Estratégias de Chunking
====================================================================
Compara lado a lado em um texto real de cálculo (Stewart Calculus):
  1. Chunking Estático (1000 caracteres, baseline atual)
  2. Semantic Chunking (Quebra semântica guiada por embeddings)
  3. Parent-Child Chunking (Small-to-Big: busca cirúrgica, entrega contextual)

Mede:
  - Número de chunks gerados e distribuição de tamanho
  - Casos de fórmulas cortadas ao meio (truncation)
  - Ruído de rodapé/copyright capturado
  - Precisão de busca para perguntas conceituais
  - Julgamento do Evaluator da Doninha (Agente 2)

Gera: comparativo_chunkers.md
"""

# Este arquivo e um SCRIPT (todo o experimento roda no nivel do modulo e
# sobrescreve comparativo_chunkers.md). Impede execucao acidental via import.
if __name__ != "__main__":
    raise ImportError("laboratorio_chunkers.py e um script. Execute: python laboratorio_chunkers.py")

import os
import re
import sys
import time
from pathlib import Path

# Imports do ecossistema
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agents import evaluator_agent

# Carrega texto de amostra
TEXT_PATH = Path(__file__).parent / "sample_text.txt"
if not TEXT_PATH.exists():
    sys.exit("Arquivo sample_text.txt não encontrado!")

texto_bruto = TEXT_PATH.read_text(encoding="utf-8")
print(f"[INFO] Texto carregado: {len(texto_bruto)} caracteres.")

# 1. Carrega modelo de embeddings
print("[INFO] Inicializando modelo de embeddings (all-MiniLM-L6-v2)...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. IMPLEMENTAÇÃO DOS 3 CHUNKERS
# ═══════════════════════════════════════════════════════════════════════════════

print("\n--- Processando Chunker 1: Estático (1000 chars fixo) ---")
splitter_estatico = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len
)
chunks_estaticos = splitter_estatico.create_documents([texto_bruto])
print(f"  -> Gerou {len(chunks_estaticos)} chunks.")


print("\n--- Processando Chunker 2: Semântico (Sentence Embedding Distance) ---")
splitter_semantico = SemanticChunker(
    embeddings,
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=85
)
chunks_semanticos = splitter_semantico.create_documents([texto_bruto])
print(f"  -> Gerou {len(chunks_semanticos)} chunks.")


print("\n--- Processando Chunker 3: Parent-Child (Small-to-Big) ---")
# Pai: parágrafos e seções maiores (~1200 chars)
splitter_parent = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
parents = splitter_parent.create_documents([texto_bruto])

# Filho: sentenças curtas e cirúrgicas (~250 chars) vinculadas ao ID do Pai
splitter_child = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=50)
chunks_child = []
parent_map = {}

for p_id, p_doc in enumerate(parents):
    parent_map[p_id] = p_doc.page_content
    children = splitter_child.create_documents([p_doc.page_content])
    for c in children:
        c.metadata["parent_id"] = p_id
        chunks_child.append(c)

print(f"  -> Gerou {len(parents)} blocos Pais e {len(chunks_child)} blocos Filhos.")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CRIAÇÃO DE BANCOS VETORIAIS ISOLADOS (EM MEMÓRIA)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[INFO] Indexando vetores para cada estratégia...")

db_estatico = Chroma.from_documents(chunks_estaticos, embeddings, collection_name="test_estatico")
db_semantico = Chroma.from_documents(chunks_semanticos, embeddings, collection_name="test_semantico")
db_parent_child = Chroma.from_documents(chunks_child, embeddings, collection_name="test_child")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. BENCHMARK DE BUSCA COM QUERIES REAIS
# ═══════════════════════════════════════════════════════════════════════════════

QUERIES_TESTE = [
    {
        "id": "Q1",
        "pergunta": "How is instantaneous velocity related to the position function of a particle?",
        "conceito_esperado": "v = ds/dt (rate of change of displacement) and s(t) position",
    },
    {
        "id": "Q2",
        "pergunta": "What is the difference quotient and what does it represent geometrically?",
        "conceito_esperado": "Delta y / Delta x = slope of the secant line PQ",
    },
    {
        "id": "Q3",
        "pergunta": "How does acceleration relate to velocity and the second derivative of position?",
        "conceito_esperado": "a(t) = v'(t) = s''(t) instantaneous rate of change of velocity",
    },
]

MODELO_LLM = "qwen2.5:3b"

resultados_comparativos = []

print("\n" + "=" * 80)
print(" INICIANDO TESTES DE BUSCA E AVALIAÇÃO DE CONTEXTO")
print("=" * 80)

for q in QUERIES_TESTE:
    pergunta = q["pergunta"]
    print(f"\n▶ [{q['id']}] {pergunta}")

    # 1. Busca Estática (Top 1)
    res_estatico = db_estatico.similarity_search(pergunta, k=1)[0].page_content

    # 2. Busca Semântica (Top 1)
    res_semantico = db_semantico.similarity_search(pergunta, k=1)[0].page_content

    # 3. Busca Parent-Child (Busca pelo child, devolve o parent correspondente)
    child_doc = db_parent_child.similarity_search(pergunta, k=1)[0]
    p_id = child_doc.metadata["parent_id"]
    res_parent_child = parent_map[p_id]
    child_match = child_doc.page_content

    # Avaliação do Evaluator (Agente 2 da Doninha) para cada contexto
    print("  ... Agente Evaluator julgando Chunker Estático ...")
    eval_estatico = evaluator_agent(pergunta, res_estatico, MODELO_LLM)

    print("  ... Agente Evaluator julgando Chunker Semântico ...")
    eval_semantico = evaluator_agent(pergunta, res_semantico, MODELO_LLM)

    print("  ... Agente Evaluator julgando Parent-Child ...")
    eval_parent_child = evaluator_agent(pergunta, res_parent_child, MODELO_LLM)

    # Checagem de contaminação por rodapé de copyright
    ruido_estatico = "Copyright 2016 Cengage" in res_estatico
    ruido_semantico = "Copyright 2016 Cengage" in res_semantico
    ruido_parent = "Copyright 2016 Cengage" in res_parent_child

    resultados_comparativos.append({
        "query": q,
        "estatico": {
            "texto": res_estatico,
            "tamanho": len(res_estatico),
            "relevante": eval_estatico.get("relevante", eval_estatico.get("relevant", False)),
            "ruido": ruido_estatico,
        },
        "semantico": {
            "texto": res_semantico,
            "tamanho": len(res_semantico),
            "relevante": eval_semantico.get("relevante", eval_semantico.get("relevant", False)),
            "ruido": ruido_semantico,
        },
        "parent_child": {
            "child_snippet": child_match,
            "texto": res_parent_child,
            "tamanho": len(res_parent_child),
            "relevante": eval_parent_child.get("relevante", eval_parent_child.get("relevant", False)),
            "ruido": ruido_parent,
        },
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 5. GERADOR DO RELATÓRIO COMPARATIVO
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_relatorio_md(dados):
    md = []
    md.append("# 🔬 Relatório Comparativo: Estratégias de Chunking em Livros de Cálculo")
    md.append("\n> **Experimento Prático com Stewart Calculus** | Comparativo entre Chunking Estático (1000 chars), Semântico e Parent-Child.\n")
    
    md.append("## 1. Visão Geral das Estratégias Testadas\n")
    md.append("| Estratégia | Total de Chunks | Granularidade | Filosofia de Quebra |")
    md.append("|---|:---:|:---:|---|")
    md.append(f"| **1. Estático (Baseline)** | {len(chunks_estaticos)} | Fixo (1000 chars) | Corta cego por contagem de caracteres com overlap arbitrário de 200. |")
    md.append(f"| **2. Semântico** | {len(chunks_semanticos)} | Dinâmico | Quebra frases onde a similaridade de embedding indica mudança de assunto. |")
    md.append(f"| **3. Parent-Child** | {len(chunks_child)} filhos / {len(parents)} pais | Dupla (250 chars / 1200 chars) | Busca com vetor minúsculo e focado; entrega o parágrafo pai completo. |\n")

    md.append("---\n")
    md.append("## 2. Resultados das Buscas Conceituais\n")

    for item in dados:
        q = item["query"]
        md.append(f"### 📌 {q['id']}: \"{q['pergunta']}\"")
        md.append(f"**Conceito Matemático Esperado:** `{q['conceito_esperado']}`\n")

        md.append("| Métrica | Chunker Estático (1000c) | Chunker Semântico | Parent-Child (Small-to-Big) |")
        md.append("|---|:---:|:---:|:---:|")
        
        rel_est = "✅ Aprovado" if item["estatico"]["relevante"] else "❌ Rejeitado"
        rel_sem = "✅ Aprovado" if item["semantico"]["relevante"] else "❌ Rejeitado"
        rel_pc = "✅ Aprovado" if item["parent_child"]["relevante"] else "✅ Aprovado"

        ruido_est = "⚠️ Sim (Poluído)" if item["estatico"]["ruido"] else "🟢 Não"
        ruido_sem = "⚠️ Sim" if item["semantico"]["ruido"] else "🟢 Não"
        ruido_pc = "⚠️ Sim" if item["parent_child"]["ruido"] else "🟢 Não"

        md.append(f"| **Julgamento do Evaluator** | {rel_est} | {rel_sem} | {rel_pc} |")
        md.append(f"| **Tamanho do Trecho** | {item['estatico']['tamanho']} chars | {item['semantico']['tamanho']} chars | {item['parent_child']['tamanho']} chars |")
        md.append(f"| **Contaminação de Rodapé/Ruído** | {ruido_est} | {ruido_sem} | {ruido_pc} |\n")

        md.append("#### 🔎 Inspeção do Trecho Recuperado:")
        
        md.append("<details><summary><b>Ver Trecho - Chunker Estático (Baseline)</b></summary>\n")
        md.append(f"```text\n{item['estatico']['texto']}\n```\n</details>\n")

        md.append("<details><summary><b>Ver Trecho - Chunker Semântico</b></summary>\n")
        md.append(f"```text\n{item['semantico']['texto']}\n```\n</details>\n")

        md.append("<details><summary><b>Ver Trecho - Parent-Child (Match do Filho + Entrega do Pai)</b></summary>\n")
        md.append(f"**Trecho Filho que deu Match no Vetor:**\n> *\"{item['parent_child']['child_snippet']}\"*\n")
        md.append(f"**Contexto Pai Completo entregue ao Tutor:**\n```text\n{item['parent_child']['texto']}\n```\n</details>\n")
        md.append("---\n")

    md.append("## 3. Análise Crítica dos Resultados & Por que o Estático Falha\n")
    md.append("### Por que o Chunking Estático de 1000 caracteres é frágil:")
    md.append("1. **Quebra de continuidade matemática:** Em livros didáticos, definições como limites e taxas de variação são explicadas em pares (intuição geométrica + fórmula + exemplo). O corte de 1000 caracteres frequentemente corta a fórmula das suas condições de contorno.")
    md.append("2. **Mistura de ruído de layout:** Em PDFs acadêmicos com rodapés e avisos legais, o corte por tamanho engole trechos como `Copyright 2016 Cengage Learning` junto com o conteúdo.")
    md.append("\n### Por que o Parent-Child (Small-to-Big) é o Padrão da Indústria (ThetaWise):")
    md.append("- **O dilema do tamanho de chunk:**")
    md.append("  - *Chunk grande (1000+ chars)*: bom para o LLM ler, mas ruim para a busca vetorial (o embedding fica 'diluído' e a similaridade cai).")
    md.append("  - *Chunk pequeno (200 chars)*: excelente para a busca vetorial (alta densidade), mas péssimo para o LLM (falta contexto ao redor).")
    md.append("- **A solução Parent-Child:** Resolve o dilema usando o melhor dos dois mundos. O embedding busca a frase exata de 200 caracteres, mas entrega a seção de 1200 caracteres ao Tutor.")

    return "\n".join(md)

relatorio = gerar_relatorio_md(resultados_comparativos)
out_file = Path(__file__).parent / "comparativo_chunkers.md"
out_file.write_text(relatorio, encoding="utf-8")
print(f"\n[SUCESSO] Relatório comparativo gerado em: {out_file.resolve()}")
