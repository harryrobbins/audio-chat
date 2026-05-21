import os
import json
import asyncio
import uuid
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

# Ensure env is loaded
load_dotenv()

# Import the agent
from agents.fact_extractor.agent import fact_extractor

async def debug_agent():
    app_name = "debug_app"
    user_id = "test_user"
    session_id = str(uuid.uuid4())
    
    session_service = InMemorySessionService()
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    
    runner = Runner(
        app_name=app_name,
        agent=fact_extractor,
        session_service=session_service
    )
    
    input_text = "The James Webb Space Telescope (JWST) is a space telescope designed to conduct infrared astronomy."
    print(f"DEBUG: Input Text: {input_text}")
    
    new_message = types.Content(parts=[types.Part(text=f"Extract facts from this text:\n\n{input_text}")])
    
    print("DEBUG: Running agent...")
    events = list(runner.run(user_id=user_id, session_id=session_id, new_message=new_message))
    
    print(f"DEBUG: Received {len(events)} events.")
    for i, event in enumerate(events):
        text = "".join([p.text for p in event.content.parts if p.text]) if event.content else "NO TEXT"
        print(f"EVENT {i} (author: {event.author}): {text}")

if __name__ == "__main__":
    asyncio.run(debug_agent())
