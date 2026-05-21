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
    Evaluate it against the original facts and the personas.
    """,
    output_schema=Critique
)
