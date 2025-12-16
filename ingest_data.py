import os
import chromadb
import ollama
import pdfplumber

# CONFIG
DB_PATH = "./chroma_db"
DATA_FOLDER = "data"
EMBEDDING_MODEL = "all-minilm"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
BATCH_SIZE = 50

# SETUP
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(name="enterprise_knowledge_base")

def read_pdf(file_path):
    text_data = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                text_data.append({"text": text, "page": i + 1})
    return text_data

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
    total = len(chunks)
    print(f"Inserting {total} chunks...")
    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        ids = [f"{item['metadata']['source']}_{i+idx}" for idx, item in enumerate(batch)]
        docs = [item['text'] for item in batch]
        metas = [item['metadata'] for item in batch]
        
        embeddings = []
        for doc in docs:
            try:
                res = ollama.embeddings(model=EMBEDDING_MODEL, prompt=doc)
                embeddings.append(res["embedding"])
            except Exception as e:
                print(f"Embedding error: {e}")
                embeddings.append([0]*384) 

        collection.add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
        print(f"Inserted batch {i//BATCH_SIZE + 1}/{(total // BATCH_SIZE) + 1}")

def main():
    if not os.path.exists(DATA_FOLDER):
        print("Data folder not found!")
        return

    files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".pdf")]
    print(f"Found {len(files)} PDFs.")

    for filename in files:
        print(f"Processing {filename}...")
        file_path = os.path.join(DATA_FOLDER, filename)
        try:
            raw_data = read_pdf(file_path)
            chunks = create_chunks(raw_data, filename)
            batch_insert(chunks)
            print(f"Done: {filename}")
        except Exception as e:
            print(f"Failed to process {filename}: {e}")

if __name__ == "__main__":
    main()
