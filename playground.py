from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.playground import Playground, serve_playground_app
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from agno.knowledge.pdf_url import PDFUrlKnowledgeBase
from agno.vectordb.pgvector import PgVector, SearchType
from sqlalchemy import create_engine, text

# ✅ SQLite storage for agent sessions
agent_storage: str = "tmp/agents.db"

# ✅ Knowledge Base Agent
DB_URL = "postgresql+psycopg://ai:ai@localhost:5532/ai"
engine = create_engine(DB_URL)
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

# Check if PDFs are loaded in database
stored_pdf_urls = get_stored_pdfs()
if stored_pdf_urls:
    print(f"✅ Loaded {len(stored_pdf_urls)} PDFs from the database!")
    knowledge_base = PDFUrlKnowledgeBase(
        urls=stored_pdf_urls,
        vector_db=vector_db,
    )
else:
    print("⚠️ No PDFs found in the database! Run `store_pdfs.py` first.")
    knowledge_base = None

# ✅ Web Agent
web_agent = Agent(
    name="Web Agent",
    model=OpenAIChat(id="gpt-4o-mini"),
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
) if knowledge_base else None

# ✅ Start Playground
agents = [web_agent, finance_agent]
if knowledge_agent:
    agents.append(knowledge_agent)
app = Playground(agents=agents).get_app()

if __name__ == "__main__":
    serve_playground_app("playground:app", reload=True)

