import os
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from typing import List

class Persona(BaseModel):
    name: str = Field(..., description="Name of the persona")
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
    """,
    output_schema=PodcastPersonas
)
