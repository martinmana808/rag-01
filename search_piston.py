import os
import pdfplumber
import re

DATA_FOLDER = "data"

def search_piston_parts():
    print(f"Searching for 'Piston' and Part Numbers (1144...) in {DATA_FOLDER}...")
    
    # Regex for Stihl part numbers (e.g., 1144 030 2000 or 1144-030-2000 or 11440302000)
    # They usually start with 1144 for MS661
    part_pattern = re.compile(r"1144[\s\-\.]?\d{3}[\s\-\.]?\d{4}")

    if not os.path.exists(DATA_FOLDER):
        print("Data folder missing.")
        return

    files = [f for f in os.listdir(DATA_FOLDER) if f.endswith(".pdf")]
    
    for filename in files:
        path = os.path.join(DATA_FOLDER, filename)
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        # Check for Piston keyword
                        if "piston" in text.lower():
                            # Look for part numbers nearby
                            matches = part_pattern.findall(text)
                            if matches:
                                print(f"FOUND Piston Candidate in: {filename} (Page {i+1})")
                                print(f"Matches: {matches}")
                                # Print context
                                idx = text.lower().find("piston")
                                start = max(0, idx - 50)
                                end = min(len(text), idx + 100)
                                print(f"Context: ...{text[start:end].replace(chr(10), ' ')}...\n")
        except Exception as e:
            print(f"Error reading {filename}: {e}")

if __name__ == "__main__":
    search_piston_parts()
