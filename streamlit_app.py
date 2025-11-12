import streamlit as st
from supabase import create_client, Client

# --- 1. SET UP CONNECTIONS ---

# We will use Streamlit's secrets manager
# We haven't added these secrets yet, but we will in the next Part.
try:
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(supabase_url, supabase_key)

    st.set_page_config(layout="wide")
    st.title("My Medium Agent System 🤖")

except Exception as e:
    st.error(f"Error connecting to Supabase. Did you set your secrets? Error: {e}")
    st.stop() # Stop the app if we can't connect

# --- 2. MAIN APP ---

st.header("Submit a New Article Idea")

topic = st.text_input("Enter your article topic:")

if st.button("Submit New Job"):
    if topic:
        try:
            # Insert the new job into the 'articles' table
            data, error = supabase.table('articles').insert({
                'topic': topic,
                'status': 'QUEUED' # This is the "in-tray" for our Colab agent
            }).execute()

            if error:
                raise Exception(error)

            st.success(f"Successfully queued job for topic: '{topic}'")
            st.balloons()
        except Exception as e:
            st.error(f"Error submitting job: {e}")
    else:
        st.warning("Please enter a topic.")

st.divider()

# --- 3. SHOW PROGRESS ---

st.header("Current Article Progress")

if st.button("Refresh Progress"):
    st.rerun() # Simple way to refresh the data

try:
    # Get all articles from the database, newest first
    response = supabase.table('articles').select('*').order('created_at', desc=True).limit(20).execute()

    articles = response.data

    if not articles:
        st.write("No articles found.")
    else:
        # Display the data in a clean table
        st.dataframe(articles)

except Exception as e:
    st.error(f"Error loading articles: {e}")
