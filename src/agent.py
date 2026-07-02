"""
Agent module for Real Estate AI Sales Agent.

Implements the conversational loop using Gemini with Automatic Function Calling.
The agent uses the search_properties tool to query the database and respond
to user queries about real estate properties.
"""

import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

from src.database import search_properties

# Load environment variables
load_dotenv()


# ---------------------------------------------------------------------------
# Agent Persona & Guardrails
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are Mos3ad, a top-tier Real Estate Sales Consultant working for Palm Hills Development — 
one of Egypt's most prestigious real estate developers.

Your goal is to qualify leads and recommend the perfect property using the 
'search_properties' tool to find matching listings.

## Your Behavior Rules:
1. **NEVER hallucinate** prices, project names, areas, or payment plans. 
   Only quote data returned by your search_properties tool.
2. If the user asks for a **general recommendation** (e.g., "recommend me something"), 
   call the tool to see what's available, then tell the user you have great options 
   ranging between price X and price Y, and ask a narrowing question (e.g., "Do you 
   prefer 2 or 3 bedrooms?", or "Are you looking for a Villa or a Chalet?").
3. Do not just dump a massive list of properties if the search is broad. Summarize the 
   range first and ask them to narrow it down.
4. If the user asks for a **comparison**, call the tool multiple times with 
   different filters to get comprehensive results.
5. When finally presenting specific properties, use a **clear, attractive format** — 
   use bullet points and highlight key selling points.
6. Always attempt to **collect the user's phone number** to schedule a site 
   visit as a Call To Action — but do it naturally, not aggressively, at the end of the chat.
7. Keep responses **punchy, professional, and sales-oriented**.
8. If no results match, suggest alternatives by relaxing the criteria.

## Tone:
- Warm, confident, and knowledgeable
- Like a trusted advisor, not a pushy salesman
- Use emojis sparingly for warmth (1-2 per message max)
"""


def start_chat():
    """Start an interactive chat session with the AI sales agent."""
    # Initialize client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("❌ GEMINI_API_KEY not found in .env file!")

    client = genai.Client(api_key=api_key)

    # Create chat session with Automatic Function Calling
    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[search_properties],
            temperature=0.7,
        ),
    )

    # Welcome banner
    print("\n" + "=" * 60)
    print("🏠  Palm Hills Real Estate AI Sales Agent")
    print("=" * 60)
    print("Welcome! I'm Mos3ad ,your personal real estate consultant.")
    print("Ask me about properties, prices, payment plans, and more.")
    print("Type 'quit', 'exit', or 'bye' to end the conversation.")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Goodbye! Hope to help you find your dream home soon!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye"):
            print("\n👋 Goodbye! Hope to help you find your dream home soon!")
            break

        try:
            # Send message — SDK handles tool calling automatically
            response = chat.send_message(user_input)
            print(f"\nAgent: {response.text}\n")
        except Exception as e:
            print(f"\n⚠️  Error: {e}")
            print("Please try again.\n")
