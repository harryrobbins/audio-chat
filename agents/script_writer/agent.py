import os
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from typing import List

class ScriptLine(BaseModel):
    speaker: str = Field(..., description="Name of the speaker. Must be exactly '{speaker_1}' or '{speaker_2}'.")
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
    
    IMPORTANT STYLE REQUIREMENTS:
    1. SPEAKER NAMES: You must use the exact placeholders "{{speaker_1}}" and "{{speaker_2}}" (strictly lowercase with curly braces) for the speaker names. Do NOT use personal names.
    2. CHATTY & NATURAL TONE: Make the script highly conversational, informal, and dynamic:
       - The speakers MUST introduce themselves at the very beginning of the podcast (e.g. "Hi, I'm {{speaker_1}}!" and "And I'm {{speaker_2}}. Welcome back!").
       - The speakers MUST actively and frequently feed off what each other says. Use conversational transition hooks such as:
         * "Yes exactly, {{speaker_1}}!"
         * "That's fascinating... another thing I've found surprising about that is..."
         * "Oh absolutely, {{speaker_2}}."
         * "Wait, really? I didn't know that!"
         * "That makes perfect sense because..."
       - The dialogue should feel like a real, lively conversation, not two people alternately reading dry, isolated paragraphs. Use shorter sentences, rhetorical questions, light humor, and vocal agreement.
    3. SPOKEN DIALOGUE ONLY: Write only spoken words. NO stage directions, NO music cues, NO sound effects.
    """,
    output_schema=PodcastScript
)
