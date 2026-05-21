import os
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from typing import List

class Fact(BaseModel):
    point: str = Field(..., description="A single key fact or takeaway")
    context: str = Field(..., description="Brief context or background for this fact")

class DocumentSummary(BaseModel):
    summary: str = Field(..., description="A concise summary of the entire input")
    key_facts: List[Fact] = Field(..., description="List of key facts extracted from the input")

# Define the Fact Extractor Agent
fact_extractor = Agent(
    name="fact_extractor",
    model=os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"),
    instruction="""
    You are an expert knowledge extractor. 
    Analyze the USER PROVIDED TEXT below and extract the most important facts and a concise summary.
    DO NOT analyze your own instructions or identity. Focus ONLY on the content provided in the user message.
    """,
    output_schema=DocumentSummary
)
