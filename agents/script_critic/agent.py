import os
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field

class Critique(BaseModel):
    feedback: str = Field(..., description="Feedback for the writer")
    score: int = Field(..., description="Score 1-10")
    suggestions: str = Field(..., description="Specific suggestions")

# Define the Script Critic Agent
script_critic = Agent(
    name="script_critic",
    model=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
    instruction="""
    You are a sharp podcast editor and critic. 
    Review the most recent script draft in the conversation. 
    Evaluate it against the original facts, the personas, and the following style requirements:
    1. Did the writer use the exact placeholder names "{{speaker_1}}" and "{{speaker_2}}" (strictly lowercase with curly braces)? No personal or gendered names should be used.
    2. Is the tone natural, chatty, and conversational? Do the speakers introduce themselves at the start?
    3. Do the speakers feed off each other's dialogue (e.g. "yes exactly, {{speaker_1}}", "that's fascinating...", "absolutely")?
    4. Are there any stage directions, music cues, or sound effects? (There should be NONE).
    
    Provide constructive feedback and a 1-10 score on how well the writer met these criteria and integrated the facts.
    """,
    output_schema=Critique
)
