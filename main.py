from dotenv import load_dotenv
# Load environment variables from .env as early as possible
load_dotenv()

import io
import os
import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from kokoro import KPipeline
from contextlib import asynccontextmanager
from typing import Dict, Optional
from routers.podcast import router as podcast_router
from routers.projects import router as projects_router
from database import init_db

# Arize Phoenix Tracing
from phoenix.otel import register
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Register Phoenix Tracer Provider
register(
    project_name=os.environ.get("PHOENIX_PROJECT_NAME", "audio-chat"),
    endpoint=os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006"),
    auto_instrument=True,
)

# Cache for pipelines to avoid reloading models on every request
pipelines: Dict[str, KPipeline] = {}

def get_pipeline(lang_code: str) -> KPipeline:
    if lang_code not in pipelines:
        try:
            pipelines[lang_code] = KPipeline(lang_code=lang_code)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load pipeline for language '{lang_code}': {str(e)}")
    return pipelines[lang_code]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    await init_db()
    # Pre-load the default American English pipeline
    print("Loading Kokoro-82M pipeline (lang='a')...")
    get_pipeline('a')
    yield
    pipelines.clear()

from fastapi.middleware.cors import CORSMiddleware
from routers.audio import router as audio_router

app = FastAPI(title="Kokoro TTS API", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(podcast_router)
app.include_router(projects_router)
app.include_router(audio_router)

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

class TTSRequest(BaseModel):
    text: str = Field(..., description="The text to convert to speech")
    voice: str = Field("af_heart", description="The voice to use (e.g., 'af_heart', 'am_adam')")
    speed: float = Field(1.0, description="Speech speed (0.5 to 2.0)")
    lang: str = Field("a", description="Language code ('a' for American English, 'b' for British, etc.)")

@app.get("/")
async def root():
    return {"message": "Kokoro-82M TTS API is running", "available_languages": list(pipelines.keys())}

@app.post("/generate")
async def generate_audio(request: TTSRequest):
    try:
        pipeline = get_pipeline(request.lang)
        
        # Generate audio chunks
        generator = pipeline(
            request.text, 
            voice=request.voice, 
            speed=request.speed, 
            split_pattern=r'\n+' # Split by newlines for better chunking if needed
        )
        
        all_audio = []
        for _, _, audio in generator:
            if audio is not None:
                all_audio.append(audio)
        
        if not all_audio:
            raise HTTPException(status_code=500, detail="No audio was generated.")
        
        # Concatenate all chunks into a single audio array
        final_audio = np.concatenate(all_audio)
        
        # Write to an in-memory WAV file
        buffer = io.BytesIO()
        # Kokoro-82M uses a 24000Hz sampling rate
        sf.write(buffer, final_audio, 24000, format='WAV')
        buffer.seek(0)
        
        return Response(content=buffer.read(), media_type="audio/wav")
        
    except Exception as e:
        print(f"Error generating audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
