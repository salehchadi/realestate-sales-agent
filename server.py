"""
FastAPI Web Server for Mos3ad — Elite AI Real Estate Concierge.

Wraps the existing Gemini agent with a web API and serves the luxury frontend.
Intercepts search_properties tool calls to return structured JSON for rich
PropertyShowcaseCard rendering on the frontend.
"""

import os
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from google import genai
from google.genai import types

from src.database import search_properties, search_properties_json

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

SYSTEM_PROMPT = """
You are Mos3ad, a top-tier Real Estate Sales Consultant working for Palm Hills Development — 
one of Egypt's most prestigious real estate developers.

Your goal is to qualify leads and recommend the perfect property using the 
'search_properties' tool to find matching listings.

## Your Behavior Rules:
1. **NEVER hallucinate** prices, project names, areas, or payment plans. 
   Only quote data returned by your search_properties tool.
2. **DATABASE-FIRST for recommendations**: If the user asks for a general recommendation
   or mentions a location/preference, ALWAYS call search_properties FIRST with whatever 
   filters you already know (e.g., location only). Then examine the results to see what 
   unit types, bedroom counts, and projects actually exist. Only THEN ask a narrowing 
   question using choices that appear in the results. For example, if results only contain 
   Townhouses, do NOT ask "Villa or Apartment?" — instead say "We have Townhouses 
   available in that area" and provide details.
3. Do not just dump a massive list of properties if the search is broad. Summarize the 
   range first and ask them to narrow it down — but only offer choices backed by data.
4. If the user asks for a **comparison**, call the tool multiple times with 
   different filters to get comprehensive results.
5. When finally presenting specific properties, use a **clear, attractive format** — 
   use bullet points and highlight key selling points.
6. Always attempt to **collect the user's phone number** to schedule a site 
   visit as a Call To Action — but do it naturally, not aggressively, at the end of the chat.
7. Keep responses **punchy, professional, and sales-oriented**.
8. **Smart alternatives when no results match**: If no results are found, call 
   search_properties again with relaxed filters (e.g., remove unit_type or bedrooms) to 
   discover what IS actually available, then present those concrete alternatives to the 
   user. Never suggest unit types or options you haven't verified exist in the database.
9. **CRITICAL — NEVER offer unverified choices**: Never present a choice between options 
   (e.g., "Villa or Apartment?", "2B or 3B?") unless you have ALREADY called 
   search_properties and confirmed ALL of those options exist in the results. If results 
   contain only one unit type or one bedroom config, state that directly instead of asking.
10. If the user writes in Arabic, respond in Arabic. If in English, respond in English.

## Tone:
- Warm, confident, and knowledgeable
- Like a trusted advisor, not a pushy salesman
- Use emojis sparingly for warmth (1-2 per message max)
"""


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

class ChatSession:
    """Holds a Gemini chat instance and tracks tool call arguments."""

    def __init__(self, client: genai.Client):
        self.chat = client.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[search_properties],
                temperature=0.7,
            ),
        )
        self.last_tool_args: list[dict] = []

    def send(self, message: str) -> str:
        """Send a user message and return the agent's text response.
        
        Also captures tool call arguments so the server can fetch
        structured property data for the frontend.
        """
        self.last_tool_args = []
        response = self.chat.send_message(message)

        # Walk through all candidates to find tool calls that were made
        # The SDK handles automatic function calling, so we inspect the
        # history to find what search_properties calls were made
        try:
            for content in self.chat.get_history():
                if content.role == "model" and content.parts:
                    for part in content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            if fc.name == "search_properties":
                                args = dict(fc.args) if fc.args else {}
                                self.last_tool_args.append(args)
        except Exception:
            pass

        return response.text or ""


# In-memory session store
sessions: dict[str, ChatSession] = {}
gemini_client: genai.Client | None = None


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the Gemini client on startup."""
    global gemini_client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not found in .env file!")
    gemini_client = genai.Client(api_key=api_key)
    print("\n" + "=" * 60)
    print("🏛️  Mos3ad Elite Concierge — Server Ready")
    print("=" * 60)
    print("Open http://localhost:8000 in your browser")
    print("=" * 60 + "\n")
    yield
    sessions.clear()


app = FastAPI(
    title="Mos3ad — Elite Real Estate Concierge",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""


class ChatResponse(BaseModel):
    text: str
    properties: list[dict] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_frontend():
    """Serve the main HTML page."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Handle a chat message.
    
    1. Forward the message to the Gemini agent
    2. If search_properties was called, also fetch structured JSON data
    3. Return both the agent text and structured property data
    """
    global gemini_client

    # Get or create session
    session_id = req.session_id or str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = ChatSession(gemini_client)

    session = sessions[session_id]

    try:
        # Clear previous tool args before sending
        session.last_tool_args = []
        
        # Send message to the agent
        agent_text = session.send(req.message)

        # If search_properties was called, fetch structured data for cards
        properties = []
        if session.last_tool_args:
            # Use the last set of tool call args to get structured data
            # (the agent may have called the tool multiple times)
            seen = set()
            for args in session.last_tool_args:
                results = search_properties_json(
                    location_keyword=args.get("location_keyword", ""),
                    unit_type=args.get("unit_type", ""),
                    max_budget=float(args.get("max_budget", 0)),
                    max_delivery_year=int(args.get("max_delivery_year", 0)),
                    bedrooms=args.get("bedrooms", ""),
                )
                for prop in results:
                    # Deduplicate by project+type+bedrooms+installment
                    key = (prop["project_name"], prop["unit_type"],
                           prop["bedrooms"], prop["installment_years"])
                    if key not in seen:
                        seen.add(key)
                        properties.append(prop)

        return ChatResponse(text=agent_text, properties=properties)

    except Exception as e:
        error_msg = str(e)
        print(f"⚠️  Chat error: {error_msg}")
        return ChatResponse(
            text="I apologize — I encountered an issue. Please try your question again.",
            properties=[]
        )


@app.post("/api/chat/reset")
async def reset_chat(req: ChatRequest):
    """Reset a chat session to start a fresh conversation."""
    session_id = req.session_id
    if session_id and session_id in sessions:
        del sessions[session_id]
    return {"status": "ok", "message": "Session reset."}
