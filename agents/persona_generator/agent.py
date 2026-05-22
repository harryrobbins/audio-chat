import os
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from typing import List

class Persona(BaseModel):
    name: str = Field(..., description="Name of the persona. Must be exactly '{speaker_1}' or '{speaker_2}'.")
    role: str = Field(..., description="Role in the podcast")
    description: str = Field(..., description="Personality description")

class PodcastPersonas(BaseModel):
    personas: List[Persona] = Field(..., description="Exactly two personas")

# Define the Persona Generator Agent
persona_generator = Agent(
    name="persona_generator",
    model=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
    instruction="""
    You are a creative producer for a high-end podcast. 
    Based on the summary of facts provided in the conversation, create two distinct and engaging personas who will discuss this topic.
    IMPORTANT: You must use the exact names "{{speaker_1}}" and "{{speaker_2}}" (strictly lowercase with curly braces) as placeholders for the two personas. Do NOT use gendered or specific personal names (like 'John' or 'Alice') to avoid mismatching with user-selected voice genders.
    """,
    output_schema=PodcastPersonas
)
