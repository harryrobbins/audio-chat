import os
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from typing import List

class ScriptLine(BaseModel):
    speaker: str = Field(..., description="Name of the speaker")
    text: str = Field(..., description="Dialogue text")

class PodcastScript(BaseModel):
    title: str = Field(..., description="Title of the podcast")
    lines: List[ScriptLine] = Field(..., description="Dialogue lines")

# Define the Script Writer Agent
script_writer = Agent(
    name="script_writer",
    model=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
    instruction="""
    You are a world-class podcast script writer. 
    Review the entire conversation history to find the core facts and the generated personas.
    Write an engaging, conversational, and informative two-person podcast script.
    """,
    output_schema=PodcastScript
)
