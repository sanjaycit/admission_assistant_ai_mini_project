# main.py - Main pipeline orchestration

from app.services.data_loader import load_csv, get_colleges_to_process, validate_csv_columns
from app.services.scraper import get_sitemap_links, crawl_homepage, filter_admission_links, scrape_page
from app.services.vector_store import build_documents, update_vector_db, inspect_vector_db
from app.core.rag import query_system
from app.core.config import DEFAULT_CSV_PATH

def process_college(college_name, website_url):
    """Process a single college: scrape and extract admission information"""
    print(f"Processing: {college_name}")

    # Try to get links from sitemap first, fallback to homepage crawling
    links = get_sitemap_links(website_url)
    if not links:
        links = crawl_homepage(website_url)

    # Filter to admission-related links
    admission_links = filter_admission_links(links)

    documents = []
    for link in admission_links:
        print(f"  Scraping: {link}")
        text = scrape_page(link)

        if not text:
            continue

        # Create documents from scraped content
        docs = build_documents(college_name, link, text)
        documents.extend(docs)

    return documents

def run_pipeline(csv_path=None, limit=None):
    """Main pipeline to process colleges and build vector database"""
    if csv_path is None:
        csv_path = DEFAULT_CSV_PATH

    # Load and validate data
    df = load_csv(csv_path)
    validate_csv_columns(df)

    # Get colleges to process
    colleges_df = get_colleges_to_process(df, limit)

    total_docs = 0

    # Process each college
    for idx, (_, row) in enumerate(colleges_df.iterrows(), 1):
        college = row['College Name']
        website = row['Weblink']

        try:
            docs = process_college(college, website)
            
            if docs:
                # Store documents immediately after processing each college
                update_vector_db(docs)
                total_docs += len(docs)
                print(f"  ✓ Stored {len(docs)} documents for {college}")
            else:
                print(f"  ⚠ No documents extracted for {college}")
        except Exception as e:
            print(f"  ✗ Error processing {college}: {e}")
            continue

    # Summary
    print(f"\n{'='*50}")
    if total_docs > 0:
        print(f"✓ Pipeline completed successfully!")
        print(f"Total documents stored: {total_docs}")
    else:
        print("⚠ No data collected from any colleges.")
    print(f"{'='*50}")

    return total_docs

# -----------------------------
# RUN
# -----------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "inspect":
            # Inspect the vector database
            inspect_vector_db()
        elif sys.argv[1] == "query" and len(sys.argv) > 2:
            # Query the system
            question = " ".join(sys.argv[2:])
            try:
                answer = query_system(question)
                print(f"\nQuestion: {question}")
                print(f"Answer: {answer}")
            except Exception as e:
                print(f"Error querying system: {e}")
        else:
            print("Usage:")
            print("  python main.py              # Run the pipeline")
            print("  python main.py inspect      # Inspect vector database")
            print("  python main.py query <question>  # Query the system")
    else:
        # Run the main pipeline
        print("Hello students! Welcome to the College Admission Information System.")
        print("We will be processing colleges to help you with your queries about admissions.")
        print("Let's get started!\n")

        run_pipeline()

# -----------------------------
# RUN
# -----------------------------

