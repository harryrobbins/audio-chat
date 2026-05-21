import io
import os
import asyncio
import numpy as np
import soundfile as sf
from pydub import AudioSegment
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from kokoro import KPipeline
from typing import Dict, List, Optional
from pydantic import BaseModel

from database import get_db
import models

router = APIRouter(prefix="/projects", tags=["audio"])

# Cache for pipelines inside the audio router to avoid circular imports and reload overhead
pipelines: Dict[str, KPipeline] = {}

def get_pipeline(lang_code: str) -> KPipeline:
    if lang_code not in pipelines:
        try:
            pipelines[lang_code] = KPipeline(lang_code=lang_code)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load pipeline for language '{lang_code}': {str(e)}"
            )
    return pipelines[lang_code]

def _synthesize_audio_thread(lines: list, p_names: list, file_path: str):
    # Setup British English Kokoro Pipeline
    pipeline = get_pipeline('b')

    # Create empty pydub AudioSegment for concatenation
    final_audio = AudioSegment.empty()

    for i, line in enumerate(lines):
        speaker = line.get("speaker", "Host")
        text = line.get("text", "")
        
        if not text.strip():
            continue

        # Choose British voice: Host is bf_alice (female), Guest is bm_george (male)
        if speaker and len(p_names) > 0 and speaker == p_names[0]:
            voice = "bf_alice"
        elif speaker and len(p_names) > 1 and speaker == p_names[1]:
            voice = "bm_george"
        else:
            # Fallback alternating
            voice = "bf_alice" if i % 2 == 0 else "bm_george"

        print(f"Synthesizing line {i+1}/{len(lines)} | Speaker: {speaker} | Voice: {voice} | Text: '{text[:40]}...'")
        
        generator = pipeline(
            text, 
            voice=voice, 
            speed=1.0, 
            split_pattern=r'\n+'
        )
        
        line_chunks = []
        for _, _, audio in generator:
            if audio is not None:
                line_chunks.append(audio)
        
        if not line_chunks:
            print(f"Warning: No audio generated for line {i+1}")
            continue

        # Concatenate chunks for the current line
        line_audio = np.concatenate(line_chunks)
        
        # Export to in-memory WAV buffer to read with PyDub
        buffer = io.BytesIO()
        sf.write(buffer, line_audio, 24000, format='WAV')
        buffer.seek(0)
        
        # Add line to final audio
        segment = AudioSegment.from_wav(buffer)
        final_audio += segment
        
        # Add a 500ms silence between dialogue lines
        final_audio += AudioSegment.silent(duration=500)

    # Export final concatenated audio to disk
    final_audio.export(file_path, format="wav")
    print(f"Concatenated audio successfully written to {file_path}")

class AudioGenerationResponse(BaseModel):
    audio_id: int
    file_path: str
    download_url: str

@router.post("/scripts/{script_id}/generate-audio", response_model=AudioGenerationResponse)
async def generate_audio(script_id: int, db: AsyncSession = Depends(get_db)):
    # 1. Fetch script from DB
    db_script = await db.get(models.Script, script_id)
    if not db_script:
        raise HTTPException(status_code=404, detail="Script not found")

    content = db_script.content
    if not content:
        raise HTTPException(status_code=400, detail="Script has no content")

    # 2. Extract dialogue lines and personas
    if isinstance(content, dict) and "script" in content:
        script_data = content["script"]
        personas_data = content.get("personas", {}).get("personas", [])
    else:
        # Fallback for old schema
        script_data = content
        personas_data = []

    lines = script_data.get("lines", [])
    if not lines:
        raise HTTPException(status_code=400, detail="Script content has no dialogue lines")

    p_names = [p["name"] for p in personas_data] if personas_data else []

    # 3. Setup output file path
    output_dir = "audio_outputs"
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"script_{script_id}.wav")

    # 4. Generate audio per line on a background thread pool to keep event loop responsive
    print(f"Generating audio for script {script_id} with {len(lines)} lines asynchronously...")
    try:
        await asyncio.to_thread(_synthesize_audio_thread, lines, p_names, file_path)
    except Exception as e:
        print(f"Audio synthesis thread failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"TTS generation failed: {str(e)}"
        )

    # 6. Save/Update Audio model in DB
    result = await db.execute(select(models.Audio).where(models.Audio.script_id == script_id))
    db_audio = result.scalars().first()

    if not db_audio:
        db_audio = models.Audio(
            script_id=script_id,
            file_path=file_path
        )
        db.add(db_audio)
    else:
        db_audio.file_path = file_path
        
    await db.commit()
    await db.refresh(db_audio)

    download_url = f"/projects/audio/{db_audio.id}"

    return AudioGenerationResponse(
        audio_id=db_audio.id,
        file_path=file_path,
        download_url=download_url
    )

@router.get("/audio/{audio_id}")
async def get_audio_file(audio_id: int, db: AsyncSession = Depends(get_db)):
    db_audio = await db.get(models.Audio, audio_id)
    if not db_audio:
        raise HTTPException(status_code=404, detail="Audio record not found")

    if not os.path.exists(db_audio.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    return FileResponse(db_audio.file_path, media_type="audio/wav", filename=f"podcast_{audio_id}.wav")
