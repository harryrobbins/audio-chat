from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from agents.podcast_flow import flow

router = APIRouter(prefix="/podcast", tags=["podcast"])

class Fact(BaseModel):
    point: str
    context: str

class DocumentSummary(BaseModel):
    summary: str
    key_facts: List[Fact]

class Persona(BaseModel):
    name: str
    role: str
    description: str

class PodcastPersonas(BaseModel):
    personas: List[Persona]

class ScriptLine(BaseModel):
    speaker: str
    text: str

class PodcastScript(BaseModel):
    title: str
    lines: List[ScriptLine]

class ExtractFactsRequest(BaseModel):
    text: str

class GenerateScriptRequest(BaseModel):
    facts: DocumentSummary
    max_loops: Optional[int] = 3

class GenerateScriptResponse(BaseModel):
    personas: PodcastPersonas
    script: PodcastScript

@router.post("/extract-facts", response_model=DocumentSummary)
async def extract_facts(request: ExtractFactsRequest):
    try:
        result = await flow.extract_facts(request.text)
        return DocumentSummary(**result)
    except Exception as e:
        print(f"Extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-script", response_model=GenerateScriptResponse)
async def generate_script(request: GenerateScriptRequest):
    try:
        result = await flow.generate_script(request.facts.model_dump(), max_loops=request.max_loops)
        return GenerateScriptResponse(**result)
    except Exception as e:
        print(f"Script generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
