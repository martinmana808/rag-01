import os
import ollama
import chromadb
from pypdf import PdfReader

# --- CONFIGURATION ---
DATA_FOLDER = "data"
EMBEDDING_MODEL = "all-minilm"
LLM_MODEL = "llama3.2"

# 1. THE LIBRARIAN (File Readers)
def read_text_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def read_pdf_file(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def chunk_text(text, chunk_size=500):
    # Simple chunker: splits text into blocks of ~500 characters
    # In a pro app, you'd use smarter splitters (by paragraph, sentence, etc.)
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        # Overlap slightly (50 chars) so we don't cut words in half at the boundary
        start += chunk_size - 50
    return chunks

# 2. THE SETUP
chroma_client = chromadb.Client()
try:
    chroma_client.delete_collection(name="my_knowledge")
except:
    pass
collection = chroma_client.create_collection(name="my_knowledge")

# 3. THE INGESTION (Reading files from folder)
print("--- 1. INGESTION (Scanning 'data' folder) ---")
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)
    print(f"Created folder '{DATA_FOLDER}'. Please put your files there and run again!")
    exit()

files = os.listdir(DATA_FOLDER)
if not files:
    print(f"The '{DATA_FOLDER}' folder is empty. Put some PDFs or TXT files in there!")
    exit()

doc_count = 0
for filename in files:
    file_path = os.path.join(DATA_FOLDER, filename)
    text_content = ""
    
    # Detect file type
    if filename.endswith(".txt"):
        text_content = read_text_file(file_path)
    elif filename.endswith(".pdf"):
        text_content = read_pdf_file(file_path)
    else:
        continue # Skip non-text files

    # Chunk and Store
    chunks = chunk_text(text_content)
    for i, chunk in enumerate(chunks):
        # We embed the chunk
        response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=chunk)
        embedding = response["embedding"]
        
        # We store it with metadata (so we know which file it came from)
        collection.add(
            ids=[f"{filename}_{i}"],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[{"source": filename}]
        )
    print(f"Processed: {filename} ({len(chunks)} chunks)")
    doc_count += 1

print(f"\n--- Ingested {doc_count} files. Ready to query! ---\n")

# 4. THE LOOP (Chat with your files)
while True:
    user_query = input("\nAsk a question (or type 'exit'): ")
    if user_query.lower() == 'exit':
        break

    # Retrieve
    response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=user_query)
    query_embedding = response["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3 # Get top 3 chunks for better context
    )
    
    # Combine retrieved chunks
    retrieved_text = "\n".join(results['documents'][0])
    sources = set(meta['source'] for meta in results['metadatas'][0])

    print(f"Reading from: {', '.join(sources)}...\n")

    # Generate
    system_prompt = f"You are a helpful assistant. Use ONLY the following context to answer the user's question. Context: {retrieved_text}"
    
    # Streaming the response so it feels faster
    stream = ollama.generate(
        model=LLM_MODEL,
        prompt=f"Context: {retrieved_text}. Question: {user_query}",
        stream=True
    )
    
    print("AI Answer: ", end="", flush=True)
    for chunk in stream:
        print(chunk['response'], end="", flush=True)
    print("\n")
