import streamlit as st
import ollama
import chromadb
import pdfplumber
import os

# --- SYSTEM CONFIGURATION (The Control Panel) ---
LLM_MODEL = "llama3.1"           # The Smart Brain
EMBEDDING_MODEL = "all-minilm"   # The Librarian
DB_PATH = "./chroma_db"          # Persistent Storage
CHUNK_SIZE = 1000                # Size of text blocks (1000 chars is a robust default)
CHUNK_OVERLAP = 200              # Context overlap to prevent cutting sentences

# --- DATABASE INITIALIZATION ---
# Using PersistentClient so your "heaps of documents" survive a restart
if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH)

chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_or_create_collection(name="enterprise_knowledge_base")

# --- ROBUST FILE PROCESSING ---
def extract_text_from_pdf(file):
    """
    Robust PDF extractor. Returns text and page numbers.
    Catches errors if a specific page is corrupt.
    """
    extracted_data = []
    try:
        with pdfplumber.open(file) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    # Basic hygiene: remove excessive whitespace
                    clean_text = " ".join(page_text.split())
                    extracted_data.append({"text": clean_text, "page": i + 1})
    except Exception as e:
        st.error(f"Error reading PDF {file.name}: {e}")
        return []
        
    return extracted_data

def create_chunks(raw_data, filename):
    """
    Splits text into overlapping chunks for the database.
    """
    all_chunks = []
    for page_entry in raw_data:
        text = page_entry["text"]
        page_num = page_entry["page"]
        
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk_text = text[start:end]
            
            # Metadata is crucial for citing sources later
            chunk_metadata = {
                "source": filename,
                "page": page_num,
                "char_start": start
            }
            
            all_chunks.append({"text": chunk_text, "meta": chunk_metadata})
            start += CHUNK_SIZE - CHUNK_OVERLAP
            
    return all_chunks

# --- UI ARCHITECTURE ---
st.set_page_config(page_title="Enterprise RAG", layout="wide")
st.title("📚 Knowledge Base (Production Mode)")

# Sidebar: Data Ingestion
with st.sidebar:
    st.header("🗄️ Document Center")
    
    # "Nuclear Option" to clear DB
    if st.button("⚠️ Wipe Database"):
        try:
            chroma_client.delete_collection("enterprise_knowledge_base")
            st.session_state.collection = chroma_client.get_or_create_collection("enterprise_knowledge_base")
            st.success("Database wiped clean.")
            st.rerun()
        except Exception as e:
            st.error(f"Error resetting DB: {e}")

    uploaded_files = st.file_uploader("Ingest Documents", accept_multiple_files=True, type=["pdf"])
    
    if uploaded_files and st.button("Process & Index"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_chunks = 0
        
        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Processing: {uploaded_file.name}...")
            
            # 1. Extract
            raw_pages = extract_text_from_pdf(uploaded_file)
            
            # 2. Chunk
            file_chunks = create_chunks(raw_pages, uploaded_file.name)
            
            # 3. Embed & Store (Batch processing would be next step for massive datasets)
            for i, chunk in enumerate(file_chunks):
                # Generate embedding
                response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=chunk["text"])
                
                # Store in Chroma
                collection.add(
                    ids=[f"{uploaded_file.name}_p{chunk['meta']['page']}_{i}"],
                    embeddings=[response["embedding"]],
                    documents=[chunk["text"]],
                    metadatas=[chunk["meta"]]
                )
            
            total_chunks += len(file_chunks)
            progress_bar.progress((idx + 1) / len(uploaded_files))
            
        status_text.success(f"✅ Ingestion Complete. Added {total_chunks} chunks to the Knowledge Base.")

# Main Interface: Chat
if "history" not in st.session_state:
    st.session_state.history = []

# Render Chat
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Query your knowledge base..."):
    # 1. Display User Message
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Retrieval Engine
    # Get vector for the question
    query_vec = ollama.embeddings(model=EMBEDDING_MODEL, prompt=prompt)["embedding"]
    
    # Search DB
    results = collection.query(query_embeddings=[query_vec], n_results=5)
    
    if not results['documents'][0]:
        st.error("No relevant documents found in the database.")
        st.stop()

    # 3. Context Construction
    context_block = ""
    sources_used = set()
    
    for i, doc_text in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        source_label = f"{meta['source']} (Pg. {meta['page']})"
        sources_used.add(source_label)
        context_block += f"\n--- [Source: {source_label}] ---\n{doc_text}\n"

    # 4. Generative AI Response
    with st.chat_message("assistant"):
        with st.expander("🔍 Evidence Retrieval (Debug)"):
            st.text(context_block)
        
        response_placeholder = st.empty()
        full_response = ""
        
        # GENERAL PURPOSE PROMPT
        # No specific logic for dates or CVs. Just pure context-based answering.
        system_prompt = f"""
        You are an expert AI Knowledge Assistant.
        
        YOUR TASK:
        Answer the user's question using ONLY the context provided below.
        
        GUIDELINES:
        - If the answer is in the context, be detailed and precise.
        - Cite your sources where possible (e.g., "According to the annual report...").
        - If the context does NOT contain the answer, explicitly state: "I cannot find that information in the provided documents."
        - Do not hallucinate or make up facts.
        
        CONTEXT:
        {context_block}
        
        USER QUESTION:
        {prompt}
        """

        stream = ollama.generate(model=LLM_MODEL, prompt=system_prompt, stream=True)
        
        for chunk in stream:
            full_response += chunk['response']
            response_placeholder.markdown(full_response + "▌")
            
        response_placeholder.markdown(full_response)
        
        # Append sources footer
        st.caption(f"📚 Sources: {', '.join(sources_used)}")
    
    st.session_state.history.append({"role": "assistant", "content": full_response})
