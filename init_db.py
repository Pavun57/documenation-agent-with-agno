#!/usr/bin/env python3
"""
Initialize the database schema for agno with proper table structure.
"""

from sqlalchemy import create_engine, text
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection URL
db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"

def init_database():
    """Initialize the database with proper schema."""
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Enable pgvector extension
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            logger.info("✅ pgvector extension enabled")
            
            # Drop existing documents table if it exists
            conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
            conn.commit()
            logger.info("✅ Dropped existing documents table")
            
            # Create documents table with proper schema
            conn.execute(text("""
                CREATE TABLE documents (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    meta_data JSONB DEFAULT '{}',
                    filters JSONB DEFAULT '{}',
                    content TEXT,
                    embedding vector(1536),
                    usage JSONB,
                    content_hash TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            conn.commit()
            logger.info("✅ Created documents table with proper schema")
            
            # Create index for better performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS documents_embedding_idx 
                ON documents USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """))
            conn.commit()
            logger.info("✅ Created vector index")
            
            logger.info("🎉 Database initialization completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Error initializing database: {str(e)}")
        raise

if __name__ == "__main__":
    init_database()
