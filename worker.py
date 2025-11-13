import os
from supabase import create_client, Client
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
# from langchain.schema import SystemMessage, HumanMessage

from langchain_core.messages import SystemMessage, HumanMessage
# from langchain.schema import HumanMessage # This might be redundant, but let's be safe. Wait, no.

# --- 1. SET UP ALL CONNECTIONS ---

try:
    # Load secrets from Render's environment variables
    SUPABASE_URL = os.environ.get('SUPABASE_URL')
    SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')

    # Set the Tavily API key as an environment variable for the tool
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

    # Connect to Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Connected to Supabase")

    # Initialize Groq LLM
    llm = ChatGroq(
        temperature=0.2,
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.1-8b-instant"
    )
    print("✅ Connected to Groq (LLM)")

    # Initialize Tavily Search Tool
    search_tool = TavilySearchResults(max_results=5)
    print("✅ Tavily Search Tool is ready")

except Exception as e:
    print(f"🔥 Error during initialization: {e}")
    raise SystemExit("Initialization failed. Check your Environment Variables.")


# --- 2. DEFINE HELPER FUNCTIONS (API Logging) ---

def log_api_call(provider, tokens=0):
    try:
        supabase.table('api_logs').insert({
            'api_provider': provider,
            'tokens_used': tokens,
            'requests_made': 1
        }).execute()
    except Exception as e:
        print(f"⚠️ Warning: Failed to log API call for {provider}. Error: {e}")

# --- 3. DEFINE THE "ASSEMBLY LINE" AGENTS ---

def run_researcher(topic: str) -> str:
    print(f"🤖 Agent 1 (Researcher) starting for topic: '{topic}'")
    try:
        search_results = search_tool.invoke(topic)
        log_api_call('tavily')
        research_data = "\n\n---\n\n".join(
            [f"Source URL: {res['url']}\nSource Content: {res['content']}" for res in search_results]
        )
        print("✅ Researcher finished.")
        return research_data
    except Exception as e:
        print(f"🔥 Researcher Error: {e}")
        return ""

def run_analyst(topic: str, research_data: str) -> str:
    print("🤖 Agent 2 (Analyst) starting...")
    system_prompt = "You are a senior research analyst. Your job is to read the provided research data and create a detailed, structured outline for a high-quality Medium article. Focus on a clear problem, key findings, and new insights. Do NOT write the article, only the outline."
    human_prompt = f"TOPIC: {topic}\n\nRESEARCH DATA:\n{research_data}\n\nPlease generate the structured outline now."
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        tokens = len(system_prompt) // 4 + len(human_prompt) // 4 + len(response.content) // 4
        log_api_call('groq', tokens)
        print("✅ Analyst finished.")
        return response.content
    except Exception as e:
        print(f"🔥 Analyst Error: {e}")
        return ""

def run_writer(topic: str, outline: str) -> str:
    print("🤖 Agent 3 (Writer) starting...")
    system_prompt = "You are a professional content writer. Your job is to write a compelling, 1000-word Medium article. Use the provided topic and detailed outline. Write in an engaging, clear, and professional tone. Format the article in Markdown."
    human_prompt = f"TOPIC: {topic}\n\nDETAILED OUTLINE:\n{outline}\n\nPlease write the full article now."
    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        tokens = len(system_prompt) // 4 + len(human_prompt) // 4 + len(response.content) // 4
        log_api_call('groq', tokens)
        print("✅ Writer finished.")
        return response.content
    except Exception as e:
        print(f"🔥 Writer Error: {e}")
        return ""

# --- 4. THE MAIN SCRIPT ---

print("\n--- 🚀 Starting Main Agent Script ---")
try:
    print("Looking for a 'QUEUED' job in Supabase...")
    response = supabase.table('articles').select('*').eq('status', 'QUEUED').limit(1).execute()

    if not response.data:
        print("No 'QUEUED' jobs found. Exiting.")
    else:
        job = response.data[0]
        job_id = job['id']
        job_topic = job['topic']
        print(f"Found job! ID: {job_id}, Topic: {job_topic}")

        supabase.table('articles').update({'status': 'RESEARCHING'}).eq('id', job_id).execute()
        research_data = run_researcher(job_topic)
        supabase.table('articles').update({'research_data': research_data}).eq('id', job_id).execute()

        supabase.table('articles').update({'status': 'ANALYZING'}).eq('id', job_id).execute()
        outline = run_analyst(job_topic, research_data)
        supabase.table('articles').update({'outline': outline}).eq('id', job_id).execute()

        supabase.table('articles').update({'status': 'DRAFTING'}).eq('id', job_id).execute()
        draft = run_writer(job_topic, outline)

        supabase.table('articles').update({
            'draft': draft,
            'status': 'PENDING_REVIEW'
        }).eq('id', job_id).execute()

        print(f"\n--- 🎉 Job {job_id} Completed! ---")

except Exception as e:
    print(f"🔥 A major error occurred: {e}")
    if 'job_id' in locals():
        supabase.table('articles').update({'status': 'FAILED'}).eq('id', job_id).execute()
        print(f"Job {job_id} marked as 'FAILED'.")

print("--- Agent script finished. ---")
