import streamlit as st
import ollama
import chromadb
import pdfplumber
import docx
import os
import datetime

# --- CONFIGURATION & SETUP ---
DB_PATH = "./chroma_db"
SYSTEM_PROMPT_FILE = "gary_config.txt"
LOG_FILE = "workshop_log.txt"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BATCH_SIZE = 50

if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH)

chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_or_create_collection(name="enterprise_knowledge_base")

# --- LOGGING ---
def log_interaction(role, content):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {role.upper()}: {content}\n")
        f.write("-" * 40 + "\n")

# --- FILE READERS ---
def read_pdf(file):
    text_data = []
    with pdfplumber.open(file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                text_data.append({"text": text, "page": i + 1})
    return text_data

def read_docx(file):
    doc = docx.Document(file)
    full_text = []
    current_chunk = ""
    page_counter = 1
    for para in doc.paragraphs:
        if len(current_chunk) > 1000:
            full_text.append({"text": current_chunk, "page": page_counter})
            current_chunk = ""
            page_counter += 1
        current_chunk += para.text + "\n"
    if current_chunk:
        full_text.append({"text": current_chunk, "page": page_counter})
    return full_text

def read_txt(file):
    text = str(file.read(), "utf-8")
    return [{"text": text, "page": 1}]

def process_file(uploaded_file):
    if uploaded_file.name.endswith(".pdf"):
        return read_pdf(uploaded_file)
    elif uploaded_file.name.endswith(".docx"):
        return read_docx(uploaded_file)
    elif uploaded_file.name.endswith((".txt", ".md")):
        return read_txt(uploaded_file)
    return []

# --- CHUNKING & BATCHING ---
def create_chunks(raw_data, filename):
    all_chunks = []
    for entry in raw_data:
        text = entry["text"]
        page = entry["page"]
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk_text = text[start:end]
            all_chunks.append({
                "text": chunk_text,
                "metadata": {"source": filename, "page": page}
            })
            start += CHUNK_SIZE - CHUNK_OVERLAP
    return all_chunks

def batch_insert(chunks):
    progress_bar = st.progress(0)
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        ids = [f"{item['metadata']['source']}_{i+idx}" for idx, item in enumerate(batch)]
        docs = [item['text'] for item in batch]
        metas = [item['metadata'] for item in batch]
        
        embeddings = []
        for doc in docs:
            try:
                res = ollama.embeddings(model="all-minilm", prompt=doc)
                embeddings.append(res["embedding"])
            except:
                embeddings.append([0]*384) 

        collection.add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
        progress_bar.progress((i + BATCH_SIZE) / len(chunks))
    progress_bar.empty()

# --- LOAD GARY'S BRAIN ---
def load_system_prompt():
    if os.path.exists(SYSTEM_PROMPT_FILE):
        with open(SYSTEM_PROMPT_FILE, "r") as f:
            return f.read()
    else:
        return "You are a helpful assistant."

# --- UI LAYOUT ---
st.set_page_config(page_title="Gary - STIHL Tech AI", layout="wide")
st.title("🔧 Gary (STIHL NZ Technician)")

with st.sidebar:
    st.header("Workshop Tools")
    try:
        models_info = ollama.list()['models']
        available_models = [m.get('model', m.get('name')) for m in models_info]
    except:
        available_models = ["gpt-oss:20b"]
    
    selected_model = st.selectbox("LLM Engine:", available_models, index=0)

    if st.button("⚠️ Clear Workbench"):
        try:
            chroma_client.delete_collection("enterprise_knowledge_base")
        except:
            pass
        st.session_state.collection = chroma_client.get_or_create_collection("enterprise_knowledge_base")
        st.rerun()

    uploaded_files = st.file_uploader("Ingest Manuals", accept_multiple_files=True, type=["pdf", "docx", "txt"])
    if uploaded_files and st.button("Ingest Docs"):
        with st.spinner("Processing..."):
            all_new_chunks = []
            for file in uploaded_files:
                raw = process_file(file)
                chunks = create_chunks(raw, file.name)
                all_new_chunks.extend(chunks)
            if all_new_chunks:
                batch_insert(all_new_chunks)
                st.success(f"Ingested {len(all_new_chunks)} blocks.")
                st.rerun()

# --- CHAT ---
if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Talk to Gary..."):
    log_interaction("user", prompt)
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 1. RETRIEVAL
    query_vec = ollama.embeddings(model="all-minilm", prompt=prompt)["embedding"]
    results = collection.query(query_embeddings=[query_vec], n_results=5)

    context_text = ""
    sources_used = set()
    if results['documents'] and results['documents'][0]:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            src = f"{meta['source']} (Pg {meta['page']})"
            sources_used.add(src)
            context_text += f"\n--- [Source: {src}] ---\n{doc}\n"
    else:
        context_text = "No local manual pages found."

    # 2. GENERATION
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        gary_instructions = load_system_prompt()
        history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in st.session_state.history[-6:]])

        final_system_prompt = f"""
### SYSTEM INSTRUCTIONS (IMMUTABLE)
{gary_instructions}

### DATABASE CONTEXT
{context_text}

### CONVERSATION HISTORY
{history_text}

### CURRENT USER INPUT
{prompt}

### EXECUTION
1. You are GARY.
2. If the user is missing information (like serial number) but says they don't have it, ACCEPT IT and move on with a warning.
3. DO NOT simulate the user.
4. Output ONLY your response.
"""

        stream = ollama.generate(model=selected_model, prompt=final_system_prompt, stream=True)
        
        for chunk in stream:
            full_response += chunk['response']
            response_placeholder.markdown(full_response + "▌")
        
        response_placeholder.markdown(full_response)
        
        if sources_used:
            st.caption(f"📚 References: {', '.join(sources_used)}")
            
        log_interaction("gary", full_response)

    st.session_state.history.append({"role": "assistant", "content": full_response})
