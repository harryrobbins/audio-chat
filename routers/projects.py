from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
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

class FactRead(BaseModel):
    id: int
    project_id: int
    document_id: int
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
