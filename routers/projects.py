from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from database import get_db
import models
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/projects", tags=["projects"])

# Pydantic schemas
class ProjectBase(BaseModel):
    name: str
    description: str = None

class ProjectCreate(ProjectBase):
    pass

class ProjectRead(ProjectBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    title: str
    content: str

class DocumentCreate(DocumentBase):
    pass

class DocumentRead(DocumentBase):
    id: int
    project_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class ProcessDocumentRequest(BaseModel):
    raw_text: str
    filename_hint: str = None

class ProcessedDocumentResponse(BaseModel):
    title: str
    content: str


class FactRead(BaseModel):
    id: int
    project_id: int
    document_id: int
    document_ids: Optional[str] = None
    point: str
    context: str
    created_at: datetime
    class Config:
        from_attributes = True

# CRUD
@router.post("/", response_model=ProjectRead)
async def create_project(project: ProjectCreate, db: AsyncSession = Depends(get_db)):
    db_project = models.Project(**project.model_dump())
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    return db_project

@router.get("/", response_model=List[ProjectRead])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Project))
    return result.scalars().all()

@router.get("/{project_id}", response_model=ProjectRead)
async def read_project(project_id: int, db: AsyncSession = Depends(get_db)):
    db_project = await db.get(models.Project, project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db_project

@router.post("/{project_id}/documents", response_model=DocumentRead)
async def create_document(project_id: int, doc: DocumentCreate, db: AsyncSession = Depends(get_db)):
    db_doc = models.Document(**doc.model_dump(), project_id=project_id)
    db.add(db_doc)
    await db.commit()
    await db.refresh(db_doc)
    return db_doc

@router.get("/{project_id}/documents", response_model=List[DocumentRead])
async def list_documents(project_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Document).where(models.Document.project_id == project_id))
    return result.scalars().all()

@router.delete("/{project_id}/documents/{document_id}")
async def delete_document(project_id: int, document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Document).where(
            models.Document.project_id == project_id,
            models.Document.id == document_id
        )
    )
    db_doc = result.scalar_one_or_none()
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found or does not belong to this project")
    
    await db.delete(db_doc)
    await db.commit()
    return {"message": "Document deleted successfully"}

from google import genai
from google.genai import types
import os

@router.post("/{project_id}/documents/process", response_model=DocumentRead)
async def process_document(project_id: int, req: ProcessDocumentRequest, db: AsyncSession = Depends(get_db)):
    # 1. Verify project exists
    db_project = await db.get(models.Project, project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # 2. Setup Gemini client
    api_key = os.getenv("GEMINI_API_KEY")
    model_id = os.getenv("GEMINI_LITE_MODEL", "gemini-3.1-flash-lite")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    
    # 3. Call Gemini Lite with structured output to get title and clean markdown content
    prompt = (
        f"You are a professional technical editor. You are given a raw document. "
        f"Analyze the document and: \n"
        f"1. Extract or generate a clean, highly descriptive, professional title for the document. "
        f"If the document has no clear title, generate a brief, descriptive one. "
        f"Use the filename hint '{req.filename_hint}' if helpful.\n"
        f"2. Clean up the document's content and format it sensibly into structured, well-formatted Markdown. "
        f"Remove useless headers, page numbers, duplicate text, or formatting noise. Organize with clean headings (H1, H2, etc.), lists, and paragraphs.\n\n"
        f"Raw document content:\n{req.raw_text}"
    )
    
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProcessedDocumentResponse,
                temperature=0.2
            )
        )
        
        # Parse the structured response
        result = ProcessedDocumentResponse.model_validate_json(response.text)
    except Exception as e:
        print(f"Error calling Gemini Lite for document processing: {e}")
        # Fallback to some basic default title and content if Gemini fails
        fallback_title = req.filename_hint or f"Uploaded Document - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        result = ProcessedDocumentResponse(
            title=fallback_title,
            content=req.raw_text
        )
        
    # 4. Save to DB
    db_doc = models.Document(
        project_id=project_id,
        title=result.title,
        content=result.content
    )
    db.add(db_doc)
    await db.commit()
    await db.refresh(db_doc)
    return db_doc

@router.post("/{project_id}/documents/upload", response_model=DocumentRead)
async def upload_document_file(
    project_id: int, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    # 1. Verify project exists
    db_project = await db.get(models.Project, project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # 2. Read file bytes and metadata
    file_bytes = await file.read()
    filename = file.filename
    mime_type = file.content_type or "application/octet-stream"
    
    # Infer mime_type if missing or generic
    if mime_type == "application/octet-stream" or not mime_type:
        if filename.endswith(".pdf"):
            mime_type = "application/pdf"
        elif filename.endswith(".docx"):
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif filename.endswith(".txt"):
            mime_type = "text/plain"
        elif filename.endswith(".md") or filename.endswith(".markdown"):
            mime_type = "text/markdown"
            
    # 3. Setup Gemini client
    api_key = os.getenv("GEMINI_API_KEY")
    model_id = os.getenv("GEMINI_LITE_MODEL", "gemini-3.1-flash-lite")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    
    # 4. Formulate prompt
    prompt = (
        f"You are a professional technical editor. You are given a document in binary or text format (filename: {filename}). "
        f"Analyze the document and: \n"
        f"1. Extract or generate a clean, highly descriptive, professional title for the document. "
        f"If the document has no clear title, generate a brief, descriptive one.\n"
        f"2. Clean up the document's content and format it sensibly into structured, well-formatted Markdown. "
        f"Remove useless headers, page numbers, duplicate text, or formatting noise. Organize with clean headings (H1, H2, etc.), lists, and paragraphs.\n\n"
        f"You must return a JSON object with keys 'title' and 'content' conforming exactly to the ProcessedDocumentResponse schema."
    )
    
    try:
        # Pass the document as inline bytes Part
        file_part = types.Part.from_bytes(
            data=file_bytes,
            mime_type=mime_type
        )
        
        response = client.models.generate_content(
            model=model_id,
            contents=[file_part, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProcessedDocumentResponse,
                temperature=0.2
            )
        )
        
        result = ProcessedDocumentResponse.model_validate_json(response.text)
    except Exception as e:
        print(f"Error calling Gemini Lite for binary file processing: {e}")
        try:
            text_content = file_bytes.decode('utf-8', errors='ignore')
        except Exception:
            text_content = f"[Binary File Content: {filename} ({len(file_bytes)} bytes)]"
        
        fallback_title = filename or f"Uploaded File - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        result = ProcessedDocumentResponse(
            title=fallback_title,
            content=text_content
        )
        
    # 5. Save to DB
    db_doc = models.Document(
        project_id=project_id,
        title=result.title,
        content=result.content
    )
    db.add(db_doc)
    await db.commit()
    await db.refresh(db_doc)
    return db_doc



from fastapi.responses import StreamingResponse
from agents.podcast_flow import flow
from utils.sse import format_sse

@router.post("/{project_id}/build-kb")
async def build_kb(project_id: int, db: AsyncSession = Depends(get_db)):
    async def event_generator():
        async for event in flow.build_knowledge_base(project_id, db):
            yield format_sse(event)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

class ScriptPrompt(BaseModel):
    prompt: str
    max_loops: int = 3

@router.post("/{project_id}/generate-script")
async def generate_script(project_id: int, request: ScriptPrompt, db: AsyncSession = Depends(get_db)):
    async def event_generator():
        async for event in flow.generate_script_stream(project_id, request.prompt, db, request.max_loops):
            yield format_sse(event)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/{project_id}/facts", response_model=List[FactRead])
async def list_facts(project_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Fact).where(models.Fact.project_id == project_id))
    return result.scalars().all()

@router.get("/{project_id}/scripts", response_model=List[dict])
async def list_scripts(project_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Script).where(models.Script.project_id == project_id))
    scripts = result.scalars().all()
    return [{"id": s.id, "title": f"{s.title} ({s.created_at})"} for s in scripts]

from sqlalchemy.orm import selectinload

@router.get("/scripts/{script_id}")
async def read_script(script_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.Script)
        .where(models.Script.id == script_id)
        .options(selectinload(models.Script.audios))
    )
    db_script = result.scalar_one_or_none()
    if not db_script:
        raise HTTPException(status_code=404, detail="Script not found")
    return db_script

@router.put("/scripts/{script_id}")
async def update_script(script_id: int, updated_content: dict, db: AsyncSession = Depends(get_db)):
    db_script = await db.get(models.Script, script_id)
    if not db_script:
        raise HTTPException(status_code=404, detail="Script not found")
    db_script.content = updated_content
    db.add(db_script)
    await db.commit()
    await db.refresh(db_script)
    return db_script

@router.delete("/scripts/{script_id}")
async def delete_script(script_id: int, db: AsyncSession = Depends(get_db)):
    import os
    db_script = await db.get(models.Script, script_id)
    if not db_script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    # Delete associated audio records and their files on disk
    result = await db.execute(
        select(models.Audio).where(models.Audio.script_id == script_id)
    )
    audios = result.scalars().all()
    for audio in audios:
        if audio.file_path and os.path.exists(audio.file_path):
            try:
                os.remove(audio.file_path)
            except Exception as e:
                print(f"Failed to delete file {audio.file_path}: {e}")
        await db.delete(audio)

    await db.delete(db_script)
    await db.commit()
    return {"status": "success", "message": "Script and associated audio files deleted successfully"}
