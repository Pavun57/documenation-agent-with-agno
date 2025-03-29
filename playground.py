from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.playground import Playground, serve_playground_app
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from agno.knowledge.pdf_url import PDFUrlKnowledgeBase
from agno.vectordb.pgvector import PgVector, SearchType
from sqlalchemy import create_engine, text

# ✅ PostgreSQL Database Connection
DB_URL = "postgresql+psycopg2://ai:ai@localhost:5532/ai"
engine = create_engine(DB_URL)

# ✅ SQLite storage for agent sessions
agent_storage: str = "tmp/agents.db"

# ✅ Connect to PgVector
vector_db = PgVector(
    table_name="documents",
    db_url=DB_URL,
    search_type=SearchType.hybrid
)

def get_stored_pdfs():
    """Retrieve all stored PDF URLs from the database."""
    query = "SELECT DISTINCT(meta_data ->> 'source_url') FROM documents WHERE meta_data ->> 'source_url' IS NOT NULL"
    with engine.connect() as conn:
        result = conn.execute(text(query)).fetchall()
    return [row[0] for row in result if row[0]]

# ✅ Load PDFs from Database
stored_pdf_urls = get_stored_pdfs()

if stored_pdf_urls:
    print(f"✅ Loaded {len(stored_pdf_urls)} PDFs from the database!")
    knowledge_base = PDFUrlKnowledgeBase(
        urls=stored_pdf_urls,
        chunk_size=1000,
        chunk_overlap=200,
        metadata_keys=["source_url", "page", "chunk", "chunk_size"],
        vector_db=vector_db,
    )
else:
    print("⚠️ No PDFs found in the database! Run `store_pdfs.py` first.")
    knowledge_base = None  # Avoids errors

# ✅ Web Agent
web_agent = Agent(
    name="Web Agent",
    model=OpenAIChat(id="gpt-4o"),
    tools=[DuckDuckGoTools()],
    instructions=["Always include sources"],
    storage=SqliteAgentStorage(table_name="web_agent", db_file=agent_storage),
    add_datetime_to_instructions=True,
    add_history_to_messages=True,
    num_history_responses=5,
    markdown=True,
)

# ✅ Finance Agent
finance_agent = Agent(
    name="Finance Agent",
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[YFinanceTools(stock_price=True, analyst_recommendations=True, company_info=True, company_news=True)],
    instructions=["Always use tables to display data"],
    storage=SqliteAgentStorage(table_name="finance_agent", db_file=agent_storage),
    add_datetime_to_instructions=True,
    add_history_to_messages=True,
    num_history_responses=5,
    markdown=True,
)

# ✅ Knowledge Base Agent (Uses Stored PDFs)
knowledge_agent = Agent(
    name="Knowledge Base Agent",
    model=OpenAIChat(id="gpt-4o-mini"),
    knowledge=knowledge_base,
    add_references=True,
    search_knowledge=True,
    instructions=[
        "Use the knowledge base to answer questions about the PDF content.",
        "Always include the PDF source URL in the response.",
        "Cite document sources with URLs.",
        "Format responses with clear sections and citations."
    ],
    storage=SqliteAgentStorage(table_name="knowledge_agent", db_file=agent_storage),
    add_datetime_to_instructions=True,
    add_history_to_messages=True,
    num_history_responses=5,
    markdown=True,
)

# ✅ Start Playground
app = Playground(agents=[web_agent, finance_agent, knowledge_agent]).get_app()

if __name__ == "__main__":
    serve_playground_app("playground:app", reload=True)

