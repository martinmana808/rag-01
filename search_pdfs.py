import os
import pdfplumber

DATA_FOLDER = "data"
SEARCH_TERM = "11448932400" # Press sleeve from old log

def search_in_pdfs():
    print(f"Searching for '{SEARCH_TERM}' in {DATA_FOLDER}...")
    if not os.path.exists(DATA_FOLDER):
        print("Data folder missing.")
        return

    files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".pdf")]
    found = False
    
    for filename in files:
        path = os.path.join(DATA_FOLDER, filename)
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and SEARCH_TERM in text:
                        print(f"FOUND in: {filename} (Page {i+1})")
                        print(f"Content snippet: {text[text.find(SEARCH_TERM)-50 : text.find(SEARCH_TERM)+100]}")
                        found = True
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            
    if not found:
        print("Not found in any PDF.")

if __name__ == "__main__":
    search_in_pdfs()
