import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load API key from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env. Please create one with your Gemini key.")

# Configure Gemini
genai.configure(api_key=api_key)

# Use the stable free-tier model
MODEL_NAME = "gemini-1.5-flash"

try:
    model = genai.GenerativeModel(MODEL_NAME)
    chat_session = model.start_chat(history=[])
    print(f"✅ Using Gemini model: {MODEL_NAME}")
except Exception as e:
    raise RuntimeError(f"❌ Failed to initialize Gemini model '{MODEL_NAME}': {e}")

def call_gemini_chat(prompt: str) -> str:
    """
    Send a prompt to Gemini and return the response text.
    Used for ReAct-style tool reasoning.
    """
    try:
        response = chat_session.send_message(prompt)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini chat call failed: {e}")
