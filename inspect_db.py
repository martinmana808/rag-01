import chromadb

DB_PATH = "./chroma_db"
client = chromadb.PersistentClient(path=DB_PATH)
try:
    collection = client.get_collection("enterprise_knowledge_base")
    all_data = collection.get()
    
    unique_sources = set()
    if all_data and all_data['metadatas']:
         unique_sources = set([m['source'] for m in all_data['metadatas']])
    
    print("--- INDEXED SOURCES ---")
    for s in sorted(unique_sources):
        print(s)
    print("-----------------------")
except Exception as e:
    print(f"Error: {e}")
