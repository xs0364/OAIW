"""
Batch import documents from D:\OAIW\knowledge\ into the ChromaDB knowledge base.
"""
import sys
import os

sys.path.insert(0, r"D:\OAIW")

from backend.parser import extract_text
from backend.addons.rag import ingest_document

KNOWLEDGE_DIR = r"D:\OAIW\knowledge"
ALLOWED_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".txt"}


def main():
    files = [f for f in os.listdir(KNOWLEDGE_DIR) if os.path.splitext(f)[1].lower() in ALLOWED_EXTS]
    print(f"Found {len(files)} documents:")
    for f in files:
        print(f"  - {f}")

    total_chunks = 0
    for fname in sorted(files):
        path = os.path.join(KNOWLEDGE_DIR, fname)
        print(f"\nProcessing: {fname}")
        try:
            text = extract_text(path)
            if not text or len(text.strip()) < 10:
                print("  SKIP: empty or unparseable content")
                continue
            print(f"  extracted: {len(text)} chars")
            chunks = ingest_document(text=text, filename=fname)
            print(f"  DONE: {chunks} chunks ingested")
            total_chunks += chunks
        except Exception as e:
            print(f"  FAILED: {e}")

    print(f"\n{'='*40}")
    print(f"Complete! {total_chunks} total chunks ingested")


if __name__ == "__main__":
    main()
