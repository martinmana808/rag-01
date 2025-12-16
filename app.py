import streamlit as st
import ollama
import chromadb
import pdfplumber
import docx
import os
import datetime
import ast
import random
import re

# --- CONFIGURATION & SETUP ---
DB_PATH = "./chroma_db"
LOG_DIR = "./logs"
SYSTEM_PROMPT_FILE = "gary_config.txt"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BATCH_SIZE = 50

# Ensure directories exist
if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH)
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Initialize Database
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_or_create_collection(name="enterprise_knowledge_base")

# --- SESSION LOGGING ---
def get_session_log_file(first_prompt):
    """Generates a unique filename based on time + first prompt slug."""
    if "log_filename" not in st.session_state:
        # Format: yymmddHHMM_prompt-slug.txt
        date_str = datetime.datetime.now().strftime("%y%m%d%H%M")
        slug = re.sub(r'[^a-z0-9]+', '-', first_prompt.lower()).strip('-')[:30]
        filename = f"{date_str}_{slug}.txt"
        st.session_state.log_filename = os.path.join(LOG_DIR, filename)
    return st.session_state.log_filename

def log_interaction(role, content):
    """Writes to the session-specific log file."""
    # Fallback to system_log if writing happens before session init
    log_file = st.session_state.get("log_filename", os.path.join(LOG_DIR, "system_debug.txt"))
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    
    with open(log_file, "a", encoding="utf-8") as f:
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
        
        # --- FIX: Clamp progress to 1.0 maximum to prevent crash ---
        current_progress = (i + BATCH_SIZE) / len(chunks)
        progress_bar.progress(min(current_progress, 1.0))
        
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

    # 1. DATABASE INSPECTOR
    st.divider()
    st.subheader("📚 Library Inspector")
    try:
        all_data = collection.get()
        if all_data and all_data['metadatas']:
            unique_sources = set([m['source'] for m in all_data['metadatas']])
            st.success(f"Indexed: {len(unique_sources)} Manuals")
            with st.expander("See File List", expanded=True):
                for s in sorted(unique_sources):
                    st.caption(f"📄 {s}")
        else:
            st.warning("Database is Empty")
    except Exception as e:
        st.error(f"DB Error: {e}")

    # 2. DEV TOOLS
    st.divider()
    with st.expander("🛠️ Dev / Debug Console", expanded=False):
        st.caption("Adjust Brain Parameters")
        temp_val = st.slider("Temperature", 0.0, 1.0, 0.1)
        smart_val = st.select_slider("Reading Depth", options=[3, 5, 10], value=5)
        show_debug = st.checkbox("Show Raw Context (X-Ray)", value=False)

    st.divider()
    if st.button("⚠️ Wipe Memory"):
        try:
            chroma_client.delete_collection("enterprise_knowledge_base")
        except: pass
        st.session_state.collection = chroma_client.get_or_create_collection("enterprise_knowledge_base")
        st.rerun()

    uploaded_files = st.file_uploader("Upload Manuals", accept_multiple_files=True, type=["pdf", "docx", "txt"])
    if uploaded_files and st.button("Ingest"):
        with st.spinner("Processing..."):
            all_new_chunks = []
            for file in uploaded_files:
                raw = process_file(file)
                chunks = create_chunks(raw, file.name)
                all_new_chunks.extend(chunks)
            if all_new_chunks:
                batch_insert(all_new_chunks)
                st.success("Done!")
                st.rerun()

# --- CHAT LOOP ---
if "history" not in st.session_state:
    st.session_state.history = []
if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

# Render History
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        # Show Thinking Block (Collapsed by default in history)
        if "thinking" in msg and msg["thinking"]:
            with st.status("Thought Process", state="complete", expanded=False):
                st.markdown(msg["thinking"])
        
        st.markdown(msg["content"])
        
        # X-Ray Debug View
        if show_debug and msg["role"] == "assistant" and "debug_context" in msg:
            with st.expander("🕵️ DEBUG: What Gary Read", expanded=True):
                for line in msg["debug_context"]:
                    st.markdown(f"- {line}")

# Suggestions Buttons (Full Width)
user_choice = None
if st.session_state.suggestions:
    st.write("Suggested replies:")
    cols = st.columns(len(st.session_state.suggestions))
    for i, suggestion in enumerate(st.session_state.suggestions):
        if cols[i].button(suggestion, key=f"sugg_{i}", use_container_width=True):
            user_choice = suggestion

# Input Handling
prompt = st.chat_input("Talk to Gary...")
if user_choice:
    prompt = user_choice 

if prompt:
    # Initialize Log File
    get_session_log_file(prompt)
    
    st.session_state.suggestions = [] 
    log_interaction("user", prompt)
    st.session_state.history.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        # 1. RETRIEVAL
        query_vec = ollama.embeddings(model="all-minilm", prompt=prompt)["embedding"]
        results = collection.query(query_embeddings=[query_vec], n_results=smart_val)

        context_text = ""
        sources_used = set()
        debug_snapshots = []
        
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                src = f"{meta['source']} (Pg {meta['page']})"
                sources_used.add(src)
                context_text += f"\n--- [Source: {src}] ---\n{doc}\n"
                debug_snapshots.append(f"**{src}:** {doc[:150]}...")
        else:
            context_text = "No local manual pages found."

        # 2. PROMPT CONSTRUCTION
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
2. FIRST: Start with a `<thinking>` block.
3. Write a **First-Person Narrative** thought process using **Bold Headers**.
4. CRITICAL: You MUST close the block with `</thinking>` BEFORE writing your response.
5. THEN: Provide your response.
6. FINAL STEP: Generate a `<suggestions>` list of 3 buttons.
   - **CRITICAL PERSPECTIVE RULE:** These buttons are for the **USER** to click. They must be written in the **FIRST PERSON ("I")**.
   - **Correct:** "I don't have the serial", "Show me the diagram", "I need torque specs".
   - **Wrong:** "Ask for serial", "Check parts", "User needs help".
   - Format: <suggestions>["Option 1", "Option 2", "Option 3"]</suggestions>
"""
        
        # 3. STREAM & RENDER
        
        # A. Status Container (Thinking Box) - Appears FIRST
        status_container = st.status("Initializing Gary...", expanded=True)
        with status_container:
            thought_placeholder = st.empty()
            
        # B. Response Container (Answer) - Appears SECOND
        response_placeholder = st.empty()
        
        stream = ollama.chat(
            model=selected_model,
            messages=[{'role': 'user', 'content': final_system_prompt}],
            stream=True,
            options={"temperature": temp_val}
        )
        
        full_buffer = ""
        is_thinking = False
        captured_thought = ""

        try:
            first_chunk = next(stream)['message']['content']
            full_buffer += first_chunk
        except StopIteration:
            pass
        
        # Check if the buffer "starts" with thinking (ignoring whitespace)
        if re.match(r'^\s*<thinking>', full_buffer):
            is_thinking = True

        for chunk in stream:
            token = chunk['message']['content']
            full_buffer += token
            
            # --- LOGIC: SEPARATE THOUGHTS FROM ANSWER ---
            
            # Check if we are currently inside a thinking block
            # We use Regex to match the opening tag cleanly
            if is_thinking:
                # We are thinking. Check if we hit the closing tag yet.
                if "</thinking>" in full_buffer:
                    is_thinking = False
                    status_container.update(label="Thought Process Complete", state="complete", expanded=False)
                    
                    # Split cleanly. The [1] element is the Answer.
                    parts = re.split(r'</\s*thinking>', full_buffer)
                    if len(parts) > 1:
                        answer_part = parts[1]
                        # Clean suggestions out of view while typing
                        clean_visible = answer_part.split("<suggestions>")[0]
                        response_placeholder.markdown(clean_visible + "▌")
                else:
                    # We are still strictly thinking. Update ONLY the thought box.
                    # Remove the opening <thinking> tag for display
                    clean_thought = re.sub(r'^\s*<thinking>', '', full_buffer).strip()
                    thought_placeholder.markdown(clean_thought)
                    
                    # Dynamic Header Logic
                    lines = clean_thought.split('\n')
                    if lines:
                        last_line = lines[-1].strip()
                        if last_line.startswith("**") and len(last_line) > 5:
                            clean_header = last_line.replace("*", "").strip()
                            status_container.update(label=f"💭 {clean_header}...")
            
            else:
                # We are NOT thinking. We are answering.
                # If we never had thoughts, or if thoughts are done.
                if "</thinking>" in full_buffer:
                     # We had thoughts previously
                     answer_part = re.split(r'</\s*thinking>', full_buffer)[-1]
                     clean_visible = answer_part.split("<suggestions>")[0]
                     response_placeholder.markdown(clean_visible + "▌")
                else:
                    # No thoughts found at all (Model skipped them). Just print everything.
                    clean_visible = full_buffer.split("<suggestions>")[0]
                    response_placeholder.markdown(clean_visible + "▌")

        # 4. FINAL CLEANUP
        status_container.update(label="Thought Process Complete", state="complete", expanded=False)
        
        suggestions_found = []
        clean_response = ""
        captured_thought = ""
        
        # Robust Regex Extraction for Final Save
        think_match = re.search(r'<thinking>(.*?)</\s*thinking>', full_buffer, re.DOTALL)
        if think_match:
            captured_thought = think_match.group(1).strip()
            clean_response = re.split(r'</\s*thinking>', full_buffer)[-1].strip()
        else:
            clean_response = full_buffer
        
        # Extract Suggestions
        sugg_match = re.search(r'<suggestions>(.*?)</suggestions>', clean_response, re.DOTALL)
        if sugg_match:
            try:
                suggestions_found = ast.literal_eval(sugg_match.group(1))
                clean_response = clean_response.split("<suggestions>")[0].strip()
            except:
                pass
        
        # Final Render
        response_placeholder.markdown(clean_response)
        
        if sources_used:
            st.caption(f"📚 References: {', '.join(sources_used)}")
            
        log_interaction("gary", f"[THOUGHTS]: {captured_thought}\n[ANSWER]: {clean_response}")
        
        st.session_state.suggestions = suggestions_found
        st.session_state.history.append({
            "role": "assistant", 
            "content": clean_response, 
            "thinking": captured_thought,
            "debug_context": debug_snapshots
        })
        st.rerun()
