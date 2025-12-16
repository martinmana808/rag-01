# 🔧 Gary: The Local AI Technician (v1.1)

**Gary** is a localized, privacy-first RAG (Retrieval-Augmented Generation) application designed to assist STIHL New Zealand technicians. It runs entirely offline on Apple Silicon (M1 Max), using a specialized "State Machine" persona to guide diagnostics rather than just retrieving text.

---

## 📍 Current Status
**Version:** v1.2 (Retrieval Optimization & Citations)
**Date:** December 16, 2025
**Stage:** **Functional Prototype / Alpha**
> *The core engine is solid. Gary can read manuals, remember them, and follow a strict diagnostic script without hallucinating user responses. He is ready for "heuristic testing" (real-world scenarios).*

---

## 🚀 Key Functionalities (v1.1)

### 1. The "Gary" Persona Engine
* **State Machine Logic:** Gary doesn't just chat; he follows a strict workflow: `Intake` → `First Take` → `Targeted Check` → `Parts Plan`.
* **External Config:** All behavioral rules, voice settings, and safety protocols are stored in `gary_config.txt`. You can tweak Gary's personality without touching the Python code.
* **Anti-Hallucination:** Strict prompt engineering prevents Gary from simulating the user or making up safety specs.

### 2. Enterprise Knowledge Base
* **Persistent Memory:** Uses **ChromaDB** to store document embeddings on the local disk (`./chroma_db`). Data survives application restarts.
* **Multi-Format Ingestion:** Supports:
    * **PDF:** Clean extraction via `pdfplumber`.
    * **Word (.docx):** Native support via `python-docx`.
    * **Text/Markdown:** For raw notes or bulletin updates.
* **Batch Indexing:** Ingests documents in batches of 50 chunks to maximize M1 Max throughput.
* **Source Provenance:** Every answer cites the specific Document Name and Page Number.

### 3. Workshop UI (Streamlit)
* **Model Selector:** Hot-swap between `gpt-oss:20b`, `llama3.1`, or `mistral` directly from the sidebar.
* **Database Inspector:** View a live list of all manuals currently indexed in the brain.
* **Session Logging:** Automatically records every conversation to `workshop_log.txt` for audit and fine-tuning.

---

## 🛠️ Tech Stack & Architecture

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Hardware** | Apple M1 Max (32GB RAM) | Local Inference Server |
| **LLM Engine** | **Ollama** | Runs the models (`gpt-oss:20b`, `all-minilm`) |
| **Backend** | **Python 3.13** | Logic orchestration |
| **Frontend** | **Streamlit** | Web Interface (Chat & Controls) |
| **Database** | **ChromaDB** | Vector Store (The Librarian) |
| **Prompting** | **Text-Injection** | Dynamic context injection from `gary_config.txt` |

---

## 📂 Project Structure

```bash
/Rag01
├── app.py                  # Main Application Logic (The Brain)
├── gary_config.txt         # System Prompt (The Persona & State Machine)
├── ingest_data.py          # [NEW] Batch PDF Ingestion Script
├── inspect_db.py           # [NEW] Database Content Inspector
├── logs/                   # Chat Logs (Auto-generated)
├── data/                   # Raw PDF/Manuals Folder
├── requirements.txt        # Dependencies
└── chroma_db/              # (Auto-generated) Persistent Database Folder
```

## 📈 Recent Updates (v1.2)
- **Inline Citations:** Gary now explicitly cites the "Source File" and "Page Number" for all technical data.
- **Deep Retrieval:** Increased default chunk reading depth to 10 to catch buried "Special Tool" references.
- **Robust Ingestion:** Added `ingest_data.py` with optimized chunk sizing (500 chars) for `all-minilm` compatibility.
- **Crash Protection:** Added "False Tool Call" recovery to prevent Ollama stream crashes.
