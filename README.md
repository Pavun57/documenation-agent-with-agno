# Tuya Documentation Search System

This system provides a comprehensive interface to search and interact with Tuya documentation using Agno with multiple specialized agents and a PostgreSQL vector database.

## Prerequisites

- Python 3.8+
- PostgreSQL database with pgvector extension
- OpenAI API key

## Database Setup

### Using Docker (Recommended)

1. Create a `docker-compose.yml` file:
```yaml
version: '3.8'
services:
  db:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_USER: ai
      POSTGRES_PASSWORD: ai
      POSTGRES_DB: ai
    ports:
      - "5532:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

2. Start the database:
```bash
docker-compose up -d
```

The database will be available at `postgresql+psycopg2://ai:ai@localhost:5532/ai`

### Manual Setup

If you prefer to set up PostgreSQL manually:

1. Install PostgreSQL and pgvector extension
2. Create the database and extension:
```sql
CREATE DATABASE ai;
CREATE EXTENSION vector;
```

## Setup

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install required packages:
```bash
pip install -U openai duckduckgo-search yfinance sqlalchemy 'fastapi[standard]' agno
```

3. Set up environment variables:
```bash
# On Windows
setx OPENAI_API_KEY sk-***

# On Linux/Mac
export OPENAI_API_KEY=sk-***
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Configure database connection:
The system expects a PostgreSQL database with the following connection string:
```
postgresql+psycopg2://ai:ai@localhost:5532/ai
```

6. Agno Setup:
- Create an account at [Agno](https://agno.ai)
- Log in to access the full Agno UI features
- Run the Agno CLI setup:
```bash
ag setup
```
- Follow the Agno documentation for additional configuration if needed

## Document Storage

1. Place your PDF URLs in `unique_document_urls.json` in the following format:
```json
{
    "unique_urls": [
        "https://example.com/doc1.pdf",
        "https://example.com/doc2.pdf"
    ]
}
```

2. Run the PDF storage script to process and store documents:
```bash
python store_pdfs.py
```

This will:
- Process PDFs in batches of 10
- Store document chunks in the PostgreSQL database
- Add metadata including source URLs, document names, and ordering
- Create vector embeddings for semantic search

## Running the Playground

Start the interactive playground interface:
```bash
python playground.py
```

The playground provides three specialized agents:

1. **Web Agent**
   - Uses GPT-4
   - Includes DuckDuckGo search capabilities
   - Always includes sources in responses

2. **Finance Agent**
   - Uses GPT-4-mini
   - Includes YFinance tools for stock data
   - Displays data in table format

3. **Knowledge Base Agent**
   - Uses GPT-4-mini
   - Searches stored PDF documentation
   - Includes source citations and references

## Features

- Interactive chat interface with multiple specialized agents
- Semantic search across stored PDF documentation
- Vector database for efficient document retrieval
- Automatic document chunking and metadata management
- Persistent agent session storage using SQLite
- Markdown formatting for better readability

## API Documentation

Once the playground is running, you can access:
- Interactive API documentation at `http://localhost:8000/docs`
- Alternative documentation at `http://localhost:8000/redoc`

## Notes

- The system processes PDFs in batches to manage system resources
- Each PDF is chunked with a size of 1000 characters and 200 character overlap
- Document metadata includes source URLs, page numbers, and chunk information
- Agent sessions are persisted in `tmp/agents.db`