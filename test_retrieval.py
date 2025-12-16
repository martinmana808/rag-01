import chromadb
import ollama

DB_PATH = "./chroma_db"
EMBEDDING_MODEL = "all-minilm"
QUERY = "I have a Stihl MS661, 177394843 serial no, but can see it running M-Tronic 3.0, I need a cylinder piston and relevant gaskets to replace a lean seized saw, give me part nos and repair instructions."
TARGET_SOURCE = "MS 661 - Technical information - 32.2013.pdf"

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_collection("enterprise_knowledge_base")

print(f"Query: {QUERY}")
print("-" * 40)

query_vec = ollama.embeddings(model=EMBEDDING_MODEL, prompt=QUERY)["embedding"]
results = collection.query(query_embeddings=[query_vec], n_results=10)

found = False
if results['documents'] and results['documents'][0]:
    for i, doc in enumerate(results['documents'][0]):
        meta = results['metadatas'][0][i]
        src = meta['source']
        page = meta['page']
        dist = results['distances'][0][i] if 'distances' in results else "N/A"
        
        print(f"Rank {i+1}: {src} (Pg {page}) - Dist: {dist}")
        if src == TARGET_SOURCE:
            found = True
            print(">>> TARGET FOUND HERE <<<")

if not found:
    print(f"\nTarget {TARGET_SOURCE} NOT found in top 10.")
