import os
import pdfplumber
import re

DATA_FOLDER = "data"
# The number user is asking for: 1144 020 1202
# We'll search for the raw digits "11440201202" in the text (ignoring spaces/dashes)
TARGET_DIGITS = "11440201202"

def clean_text(text):
    """Remove all non-digit characters."""
    return re.sub(r'[^0-9]', '', text)

def search_files():
    print(f"Searching for {TARGET_DIGITS} (flexible format) in {DATA_FOLDER}...")
    
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
                    if text:
                        # 1. Direct string match (e.g. "1144 020 1202")
                        if "1144 020 1202" in text:
                            print(f"[DIRECT MATCH] Found in: {filename} (Page {i+1})")
                            print_context(text, "1144 020 1202")
                            found = True
                        
                        # 2. Flattened match (e.g. "11440201202" or "1144-020-1202")
                        flat_text = clean_text(text)
                        if TARGET_DIGITS in flat_text:
                            # If we found it in flattened text but not direct, try to find the actual representation
                            print(f"[FUZZY MATCH] Found in: {filename} (Page {i+1})")
                            # Try to find the substring in original text that roughly matches
                            # This is tricky, just printing a chunk of the page might be best or a regex search
                            match = re.search(r"1144[\s\-\.]?020[\s\-\.]?1202", text)
                            if match:
                                print(f"  > Actual text: '{match.group(0)}'")
                                print_context(text, match.group(0))
                            else:
                                print("  > (Could not extract exact string, but digits match)")
                            found = True
                            
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    if not found:
        print("❌ Part number NOT found in any file.")

def print_context(text, keyword):
    idx = text.find(keyword)
    if idx != -1:
        start = max(0, idx - 50)
        end = min(len(text), idx + 100)
        print(f"  > Context: ...{text[start:end].replace(chr(10), ' ')}...\n")

if __name__ == "__main__":
    search_files()
