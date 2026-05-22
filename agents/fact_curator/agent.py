import os
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from typing import List

class CuratedFact(BaseModel):
    point: str = Field(
        ..., 
        description="A clear, highly informative, synthesized fact point. Keep it professional, objective, and detailed."
    )
    context: str = Field(
        ..., 
        description="A synthesized context or collection of original quotes that supports this fact. Combine multiple contexts/quotes if they are merged, keeping it highly readable."
    )
    document_ids: List[int] = Field(
        ..., 
        description="The combined list of all unique document IDs that support/cite this fact. Do not lose any supporting document references."
    )

class CurationResponse(BaseModel):
    curated_facts: List[CuratedFact] = Field(
        ..., 
        description="The final curated, deduplicated, and unified list of facts."
    )

# Define the Fact Curator Agent
fact_curator = Agent(
    name="fact_curator",
    model=os.environ.get("GEMINI_MODEL", "gemini-flash-latest"),
    instruction="""
    You are an expert knowledge curator. 
    Your task is to perform a final global curation pass over a compiled list of facts extracted from multiple source documents.
    
    You will be provided with:
    - A list of compiled facts, where each fact has a 'point', 'context', and a list of supporting 'document_ids'.
    
    Your goals:
    1. Deduplicate any facts that are highly similar, redundant, or overlapping.
    2. Group and synthesize related points into comprehensive, clean, and professional fact entries.
    3. When merging overlapping facts, make sure to COMBINE and merge their 'document_ids' lists so we don't lose any source citations.
    4. Synthesize the contexts/quotes beautifully into a concise and well-formatted block.
    5. Clean up the tone and style to ensure all facts are consistent, objective, and highly professional.
    
    Always output a JSON object adhering exactly to the CurationResponse schema.
    """,
    output_schema=CurationResponse
)
