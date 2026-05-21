import os
import json
import asyncio
import uuid
from google.adk import Runner, Agent
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

# Ensure env is loaded
load_dotenv()

async def inspect_request(callback_context, llm_request):
    print("\n--- DEBUG: LLM REQUEST ---")
    print(f"Model: {llm_request.model}")
    for i, content in enumerate(llm_request.contents):
        role = content.role or "unknown"
        text = "".join([p.text for p in content.parts if p.text])
        print(f"Content {i} ({role}): {text}")
    print("--------------------------\n")
    return None

async def debug_agent():
    app_name = "debug_app"
    user_id = "test_user"
    session_id = str(uuid.uuid4())
    
    session_service = InMemorySessionService()
    await session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    
    test_agent = Agent(
        name="test_agent",
        model=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
        instruction="You are a helpful assistant.",
        before_model_callback=inspect_request
    )
    
    runner = Runner(
        app_name=app_name,
        agent=test_agent,
        session_service=session_service
    )
    
    new_message = types.Content(parts=[types.Part(text="What is the capital of France?")])
    
    print("DEBUG: Running agent...")
    events = list(runner.run(user_id=user_id, session_id=session_id, new_message=new_message))
    
    final_text = "".join([p.text for p in events[-1].content.parts if p.text])
    print(f"DEBUG: Final Response: {final_text}")

if __name__ == "__main__":
    asyncio.run(debug_agent())
