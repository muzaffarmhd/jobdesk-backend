import os
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Step 1: Load Environment Variables ---
# This line looks for a .env file in the current directory and loads
# its key-value pairs into the environment for your script to use.
load_dotenv()

# --- Step 2: Get Supabase Credentials ---
# We safely retrieve the URL and Key from the loaded environment variables.
# os.environ.get() will return None if the variable is not found,
# preventing the app from crashing.
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# --- Step 3: Initialize the Supabase Client ---
# We initialize the client outside of the request/response cycle so it can be
# reused across the application.
supabase: Client = None # Define the variable with a default value

# A try-except block is used for robustness. If the URL or key is missing,
# create_client will raise an error.
try:
    if url and key:
        supabase = create_client(url, key)
    else:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in your .env file.")
except Exception as e:
    print(f"Error creating Supabase client: {e}")