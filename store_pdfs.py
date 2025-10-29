from agno.knowledge.pdf_url import PDFUrlKnowledgeBase
from agno.vectordb.pgvector import PgVector, SearchType
from sqlalchemy import create_engine, text
import json
import logging
import concurrent.futures
import math
from typing import List, Dict
import time
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection URL
db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"

def process_pdf_batch(pdf_batch: List[Dict], vector_db: PgVector, batch_num: int) -> List[str]:
    """Process a batch of PDFs and store them in the database.
    Returns a list of failed PDF URLs."""
    failed_pdfs = []
    try:
        logger.info(f"Processing batch {batch_num} with {len(pdf_batch)} PDFs...")
        
        # Process each PDF individually
        for pdf in pdf_batch:
            try:
                # Create knowledge base for this PDF
                knowledge_base = PDFUrlKnowledgeBase(
                    urls=[pdf['url']],
                    vector_db=vector_db,
                )
                
                # Load PDF into DB
                knowledge_base.load(upsert=True)
                
                # Update metadata for this PDF
                with engine.connect() as conn:
                    # Get the number of chunks for this PDF
                    chunk_count = conn.execute(
                        text("SELECT COUNT(*) FROM documents WHERE meta_data->>'source_url' = :url"),
                        {"url": pdf['url']}
                    ).scalar()
                    
                    if chunk_count:
                        # Update metadata for all chunks of this PDF
                        conn.execute(
                            text("""
                                UPDATE documents 
                                SET meta_data = jsonb_set(
                                    jsonb_set(
                                        meta_data,
                                        '{doc_name}',
                                        cast(:doc_name as jsonb)
                                    ),
                                    '{doc_order}',
                                    cast(:doc_order as jsonb)
                                )
                                WHERE meta_data->>'source_url' = :url
                            """),
                            {
                                "url": pdf['url'],
                                "doc_name": json.dumps(pdf['name']),
                                "doc_order": json.dumps(pdf['order'])
                            }
                        )
                        conn.commit()
                        logger.info(f"Updated metadata for {pdf['name']} with {chunk_count} chunks")
                    else:
                        # If no chunks found, try to update by URL pattern
                        conn.execute(
                            text("""
                                UPDATE documents 
                                SET meta_data = jsonb_set(
                                    jsonb_set(
                                        jsonb_set(
                                            meta_data,
                                            '{source_url}',
                                            cast(:url as jsonb)
                                        ),
                                        '{doc_name}',
                                        cast(:doc_name as jsonb)
                                    ),
                                    '{doc_order}',
                                    cast(:doc_order as jsonb)
                                )
                                WHERE id IN (
                                    SELECT id 
                                    FROM documents 
                                    WHERE meta_data->>'source_url' IS NULL 
                                    ORDER BY id 
                                    LIMIT 5
                                )
                            """),
                            {
                                "url": json.dumps(pdf['url']),
                                "doc_name": json.dumps(pdf['name']),
                                "doc_order": json.dumps(pdf['order'])
                            }
                        )
                        conn.commit()
                        logger.info(f"Updated metadata for {pdf['name']} using URL pattern")
            except Exception as e:
                logger.error(f"Error processing PDF {pdf['name']}: {str(e)}")
                failed_pdfs.append(pdf['url'])
                continue
        
        return failed_pdfs
    except Exception as e:
        logger.error(f"Error in batch {batch_num}: {str(e)}")
        return [pdf['url'] for pdf in pdf_batch]

def main():
    try:
        # Read PDF URLs from JSON file
        json_path = 'test.json'
        if not os.path.exists(json_path):
            json_path = os.path.join('backend', 'unique_document_urls.json')
            if not os.path.exists(json_path):
                raise FileNotFoundError(f"Could not find unique_document_urls.json in current directory or backend directory")
        
        with open(json_path, 'r') as f:
            data = json.load(f)
            pdf_urls = [
                {
                    "url": url,
                    "name": url.split('/')[-1].replace('%20', ' ').replace('.pdf', ''),
                    "order": idx + 1
                }
                for idx, url in enumerate(data['unique_urls'])
            ]
        logger.info(f"Loaded {len(pdf_urls)} URLs from {json_path}")

        # Connect to database
        global engine
        engine = create_engine(db_url)

        # Clear existing documents (if table exists)
        with engine.connect() as conn:
            try:
                conn.execute(text("DELETE FROM documents"))
                conn.commit()
                logger.info("Cleared existing documents from database")
            except Exception as e:
                logger.info("Documents table doesn't exist yet, will be created automatically")
                conn.rollback()

        # Create vector DB instance
        vector_db = PgVector(
            table_name="documents",
            db_url=db_url,
            search_type=SearchType.hybrid
        )

        # Process PDFs in batches
        BATCH_SIZE = 10  # Adjust based on system resources
        total_pdfs = len(pdf_urls)
        num_batches = math.ceil(total_pdfs / BATCH_SIZE)
        
        success_count = 0
        failed_pdfs = []

        for batch_num in range(num_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, total_pdfs)
            current_batch = pdf_urls[start_idx:end_idx]
            
            logger.info(f"Processing batch {batch_num + 1}/{num_batches} ({len(current_batch)} PDFs)")
            
            batch_failed = process_pdf_batch(current_batch, vector_db, batch_num + 1)
            failed_pdfs.extend(batch_failed)
            success_count += len(current_batch) - len(batch_failed)
            
            # Add a small delay between batches to prevent overwhelming the system
            if batch_num < num_batches - 1:
                time.sleep(2)

        logger.info(f"✅ Completed processing {success_count}/{total_pdfs} PDFs successfully")
        if failed_pdfs:
            logger.warning(f"Failed to process {len(failed_pdfs)} PDFs:")
            for url in failed_pdfs:
                logger.warning(f"  - {url}")

        # Final verification
        with engine.connect() as conn:
            # Check total count
            count_result = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
            logger.info(f"Total documents in database: {count_result}")
            
            # Check unique source URLs with proper ordering
            urls_result = conn.execute(text("""
                SELECT DISTINCT ON ((meta_data->>'doc_order')::int)
                    meta_data->>'source_url' as source_url,
                    meta_data->>'doc_name' as doc_name,
                    meta_data->>'doc_order' as doc_order,
                    (meta_data->>'doc_order')::int as order_num
                FROM documents
                WHERE meta_data->>'source_url' IS NOT NULL
                ORDER BY order_num, id
            """)).fetchall()
            
            logger.info("\nStored PDFs in order:")
            for row in urls_result:
                logger.info(f"  - {row[1]} (Order: {row[2]})")

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
