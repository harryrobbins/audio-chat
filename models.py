from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import datetime

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    facts = relationship("Fact", back_populates="project", cascade="all, delete-orphan")
    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    title = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

    project = relationship("Project", back_populates="documents")
    facts = relationship("Fact", back_populates="document", cascade="all, delete-orphan")

class Fact(Base):
    __tablename__ = "facts"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    document_id = Column(Integer, ForeignKey("documents.id"))
    point = Column(Text)
    context = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

    project = relationship("Project", back_populates="facts")
    document = relationship("Document", back_populates="facts")

class Script(Base):
    __tablename__ = "scripts"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    title = Column(String)
    content = Column(JSON)  # Store the list of script lines
    prompt = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.now)

    project = relationship("Project", back_populates="scripts")
    audios = relationship("Audio", back_populates="script", cascade="all, delete-orphan")

class Audio(Base):
    __tablename__ = "audios"
    id = Column(Integer, primary_key=True, index=True)
    script_id = Column(Integer, ForeignKey("scripts.id"))
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)

    script = relationship("Script", back_populates="audios")
