"""
Command-line interface and entrypoint for testing the Web RAG system directly via CLI.
"""
# main.py - Main entrypoint for the Web RAG system

import sys
from pathlib import Path

# Add the 'backend' directory to sys.path so 'app' is recognized as a package
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.web_rag import query_web_system

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "query" and len(sys.argv) > 2:
            question = " ".join(sys.argv[2:])
            print(f"\n[USER QUESTION] {question}")
            try:
                answer = query_web_system(question)
                print(f"\n[FINAL ANSWER]\n{answer}")
            except Exception as e:
                print(f"Error querying system: {e}")
        elif sys.argv[1] == "inspect":
            from app.services.persistent_store import get_db
            try:
                db = get_db()
                count = db._collection.count()
                print(f"\n[INSPECT] ChromaDB cache currently contains {count} stored chunk(s).")
            except Exception as e:
                print(f"Error inspecting database: {e}")
        else:
            print("Usage:")
            print("  python main.py query <question>  # Query the Web RAG system")
            print("  python main.py inspect           # Inspect the ChromaDB vector storage")
    else:
        print("Hello students! Welcome to the College Admission Information System.")
        print("This system uses live Web Search + RAG to answer your questions.")
        print("\nUsage:")
        print("  python main.py query <question>")
        print("  python main.py inspect")
        print("\nExample:")
        print("  python main.py query \"latest 2026 admission fee for Stanford\"")

if __name__ == "__main__":
    main()
