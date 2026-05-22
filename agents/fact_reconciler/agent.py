import os
from google.adk import Agent
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from typing import List, Optional

class ReconciledFact(BaseModel):
    existing_fact_id: Optional[int] = Field(
        None, 
        description="If this new candidate fact matches or extends an existing fact, provide the 0-based integer ID of that existing fact. If it is a brand-new fact, set this to null."
    )
    point: str = Field(
        ..., 
        description="The point/assertion. If extending an existing fact, synthesize the existing point and the new candidate fact into a single, comprehensive point. If it's a new fact, use the new candidate fact's point."
    )
    context: str = Field(
        ..., 
        description="The context/quote supporting this fact. If extending an existing fact, combine/append the new context with the existing context in a clean, readable way. If it's a new fact, use the new context."
    )

class ReconciliationResponse(BaseModel):
    reconciled_facts: List[ReconciledFact] = Field(
        ..., 
        description="The list of all facts that are created or updated as a result of merging the new candidate facts into the existing facts."
    )

# Define the Fact Reconciler Agent
fact_reconciler = Agent(
    name="fact_reconciler",
    model=os.environ.get("GEMINI_MODEL", "gemini-flash-latest"),
    instruction="""
    You are an expert knowledge synthesis agent.
    Your task is to reconcile a set of NEW candidate facts extracted from a new document into an EXISTING compiled list of facts.
    
    You will be provided with:
    1. A list of EXISTING compiled facts (each with a 0-based integer ID).
    2. A list of NEW candidate facts.
    
    For each new candidate fact:
    - Carefully evaluate whether it matches, supports, or extends an already existing fact in the compiled list.
    - If it matches or extends an existing fact: set 'existing_fact_id' to the 0-based integer ID of that existing fact. Rewrite and synthesize the 'point' and 'context' to merge both the new and existing knowledge cleanly and comprehensively.
    - If it represents a brand-new fact that does not overlap or match any existing fact, set 'existing_fact_id' to null, and write its point and context as a new entry.
    
    Be objective and preserve the original nuance, assertions, and verification quotes. Avoid generating duplicates.
    """,
    output_schema=ReconciliationResponse
)
