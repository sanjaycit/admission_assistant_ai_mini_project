# ingest.py - Data ingestion pipeline for creating vector database

import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.vector_store import store_vector_db
from langchain_core.documents import Document

# Create sample documents for testing
sample_documents = [
    Document(
        page_content="Anna University offers undergraduate and postgraduate programs in engineering. Admission is based on entrance examinations and merit-based selection.",
        metadata={
            "college": "Anna University",
            "source": "https://www.annauniv.edu/admission"
        }
    ),
    Document(
        page_content="The university provides scholarships for meritorious students. International students are welcome to apply through separate admission channels.",
        metadata={
            "college": "Anna University",
            "source": "https://www.annauniv.edu/scholarships"
        }
    ),
    Document(
        page_content="Indian Institute of Technology Madras (IITM) conducts JEE Advanced for admission to undergraduate programs. Postgraduate admissions are based on GATE scores.",
        metadata={
            "college": "IIT Madras",
            "source": "https://www.iitm.ac.in/admission"
        }
    ),
    Document(
        page_content="IIT Madras offers research-oriented programs with world-class faculty. The campus is equipped with modern laboratories and computing facilities.",
        metadata={
            "college": "IIT Madras",
            "source": "https://www.iitm.ac.in/research"
        }
    ),
    Document(
        page_content="Loyola College offers admission through merit-based and entrance exam based procedures. The college emphasizes on holistic education and character development.",
        metadata={
            "college": "Loyola College",
            "source": "https://www.loyolacollege.edu/admission"
        }
    ),
]

if __name__ == "__main__":
    print("Creating sample vector database...")
    store_vector_db(sample_documents)
    print(f"✓ Sample vector database created with {len(sample_documents)} documents")
    print("\nNow you can inspect it with: python main.py inspect")
