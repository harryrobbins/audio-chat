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

try:
    from pocket_tts import TTSModel
    POCKET_TTS_AVAILABLE = True
except ImportError:
    POCKET_TTS_AVAILABLE = False

VOICE_METADATA = {
    # Kokoro-82M
    "bf_alice": {"name": "Alice", "gender": "female"},
    "bf_emma": {"name": "Emma", "gender": "female"},
    "bm_george": {"name": "George", "gender": "male"},
    "af_heart": {"name": "Heart", "gender": "female"},
    "af_bella": {"name": "Bella", "gender": "female"},
    "am_adam": {"name": "Adam", "gender": "male"},
    "am_michael": {"name": "Michael", "gender": "male"},
    
    # Pocket TTS / gTTS
    "alba": {"name": "Alba", "gender": "female"},
    "fantine": {"name": "Fantine", "gender": "female"},
    "cosette": {"name": "Cosette", "gender": "female"},
    "marius": {"name": "Marius", "gender": "male"},
    "javert": {"name": "Javert", "gender": "male"},
    "jean": {"name": "Jean", "gender": "male"},
    "en": {"name": "US Host", "gender": "female"},
    "en-uk": {"name": "UK Host", "gender": "female"},
    "en-au": {"name": "AU Host", "gender": "female"},
    "es": {"name": "Spanish Host", "gender": "female"},
    "fr": {"name": "French Host", "gender": "female"},
    
    # Gemini Flash TTS
    "Aoede": {"name": "Aoede", "gender": "female"},
    "Kore": {"name": "Kore", "gender": "female"},
    "Puck": {"name": "Puck", "gender": "male"},
    "Charon": {"name": "Charon", "gender": "male"},
    "Fenrir": {"name": "Fenrir", "gender": "male"},
}

def _synthesize_audio_thread(lines: list, p_names: list, file_path: str, model_name: str, settings: dict, progress_queue=None):
    try:
        _synthesize_audio_thread_impl(lines, p_names, file_path, model_name, settings, progress_queue)
    except Exception as e:
        import traceback
        traceback.print_exc()
        if progress_queue:
            try:
                progress_queue.put({"type": "error", "error": str(e)})
            except Exception:
                pass
        raise e

def _synthesize_audio_thread_impl(lines: list, p_names: list, file_path: str, model_name: str, settings: dict, progress_queue=None):
    # Parse settings with defaults
    speed = float(settings.get("speed", 1.0))
    voice_host = settings.get("voice_host")
    voice_guest = settings.get("voice_guest")

    # Create empty pydub AudioSegment for concatenation
    final_audio = AudioSegment.empty()

    # Cache for voice prompt states to prevent repeated HF downloads / Mimi encodings
    voice_states_cache = {}

    # Load pipelines / engines as needed
    if model_name == "kokoro-82m":
        # Kokoro voice defaults: host = bf_alice, guest = bm_george
        if not voice_host: voice_host = "bf_alice"
        if not voice_guest: voice_guest = "bm_george"
        
        # Determine language code from voice prefix
        lang_code = 'b' # Default British
        if voice_host.startswith('a') or voice_guest.startswith('a'):
            lang_code = 'a' # American English
            
        pipeline = get_pipeline(lang_code)

    elif model_name == "pocket-tts":
        # Pocket TTS voice defaults: host = alba, guest = marius
        if not voice_host: voice_host = "alba"
        if not voice_guest: voice_guest = "marius"
        
        # Load pocket tts model if available
        pocket_model = None
        if POCKET_TTS_AVAILABLE:
            try:
                print("Loading Kyutai Pocket TTS model...")
                pocket_model = TTSModel.load_model()
            except Exception as e:
                print(f"Failed to load Kyutai Pocket TTS model (gated/HF access/network issue): {e}. Falling back to gTTS.")
        else:
            print("pocket-tts package is not available or imported. Falling back to gTTS.")

    elif model_name == "gemini-flash-tts":
        # Gemini voices: Puck, Charon, Kore, Fenrir, Aoede
        # host = Aoede, guest = Charon
        if not voice_host: voice_host = "Aoede"
        if not voice_guest: voice_guest = "Charon"
        
        # Initialize Google GenAI client
        from google import genai
        from google.genai import types
        try:
            client = genai.Client()
        except Exception as e:
            print(f"Failed to initialize Google GenAI Client: {e}")
            raise RuntimeError(f"Google GenAI Client error: {e}. Please ensure GEMINI_API_KEY is configured.")

    # Resolve speaker names
    voice_host_meta = VOICE_METADATA.get(voice_host, {})
    voice_guest_meta = VOICE_METADATA.get(voice_guest, {})
    
    speaker_1_name_default = voice_host_meta.get("name", "Speaker 1")
    speaker_2_name_default = voice_guest_meta.get("name", "Speaker 2")
    
    speaker_1_name = settings.get("speaker_1_name") or speaker_1_name_default
    speaker_2_name = settings.get("speaker_2_name") or speaker_2_name_default

    for i, line in enumerate(lines):
        speaker_raw = str(line.get("speaker") or "Host")
        text_raw = str(line.get("text") or "")
        
        if not text_raw.strip():
            continue

        # Map current speaker to host/guest voice
        is_host = True
        speaker_clean = speaker_raw.strip()
        if speaker_clean in ["{speaker_1}", speaker_1_name]:
            is_host = True
        elif speaker_clean in ["{speaker_2}", speaker_2_name]:
            is_host = False
        elif len(p_names) > 0 and speaker_clean == p_names[0].strip():
            is_host = True
        elif len(p_names) > 1 and speaker_clean == p_names[1].strip():
            is_host = False
        else:
            is_host = (i % 2 == 0)

        current_voice = voice_host if is_host else voice_guest

        # Perform placeholder substitutions
        speaker = speaker_raw.replace("{speaker_1}", speaker_1_name).replace("{speaker_2}", speaker_2_name)
        text = text_raw.replace("{speaker_1}", speaker_1_name).replace("{speaker_2}", speaker_2_name)

        status_msg = f"Synthesizing line {i+1}/{len(lines)} ({speaker}: '{text[:35]}...')"
        print(status_msg)
        if progress_queue:
            progress_queue.put({"type": "progress", "status": status_msg})

        # Create temporary buffer for line segment
        line_segment = None

        if model_name == "kokoro-82m":
            # Kokoro Synthesis
            generator = pipeline(
                text, 
                voice=current_voice, 
                speed=speed, 
                split_pattern=r'\n+'
            )
            line_chunks = []
            for _, _, audio in generator:
                if audio is not None:
                    line_chunks.append(audio)
            
            if line_chunks:
                line_audio = np.concatenate(line_chunks)
                buffer = io.BytesIO()
                sf.write(buffer, line_audio, 24000, format='WAV')
                buffer.seek(0)
                line_segment = AudioSegment.from_wav(buffer)
            else:
                print(f"Warning: No audio generated for line {i+1} using Kokoro-82M")

        elif model_name == "pocket-tts":
            # Pocket TTS Synthesis
            if pocket_model is not None:
                try:
                    # Kyutai pocket-tts generate
                    # Predefined catalog voices in pocket-tts (can be passed as string names to avoid requiring voice cloning weights)
                    POCKET_CATALOG_VOICES = {
                        "alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"
                    }
                    
                    if current_voice in POCKET_CATALOG_VOICES:
                        prompt_arg = current_voice
                    else:
                        VOICE_PROMPTS = {
                            "alba": "hf://kyutai/tts-voices/alba-mackenna/casual.wav",
                            "marius": "hf://kyutai/tts-voices/marius-mackenna/casual.wav",
                            "javert": "hf://kyutai/tts-voices/javert-mackenna/casual.wav",
                            "jean": "hf://kyutai/tts-voices/jean-mackenna/casual.wav",
                            "fantine": "hf://kyutai/tts-voices/fantine-mackenna/casual.wav",
                            "cosette": "hf://kyutai/tts-voices/cosette-mackenna/casual.wav",
                            "eponine": "hf://kyutai/tts-voices/eponine-mackenna/casual.wav",
                            "azelma": "hf://kyutai/tts-voices/azelma-mackenna/casual.wav",
                        }
                        prompt_arg = VOICE_PROMPTS.get(current_voice, "alba")
                    
                    if prompt_arg not in voice_states_cache:
                        print(f"Loading/Encoding voice prompt: {prompt_arg}...")
                        voice_states_cache[prompt_arg] = pocket_model.get_state_for_audio_prompt(prompt_arg)
                        
                    voice_state = voice_states_cache[prompt_arg]
                    
                    # Generate audio tensor
                    audio_tensor = pocket_model.generate_audio(voice_state, text)
                    
                    # Convert PyTorch tensor to numpy
                    audio_numpy = audio_tensor.cpu().numpy()
                    if audio_numpy.ndim == 2 and audio_numpy.shape[0] == 1:
                        audio_numpy = audio_numpy[0]
                    elif audio_numpy.ndim == 2:
                        audio_numpy = audio_numpy.T
                        
                    buffer = io.BytesIO()
                    sf.write(buffer, audio_numpy, pocket_model.sample_rate, format='WAV')
                    buffer.seek(0)
                    line_segment = AudioSegment.from_wav(buffer)
                except Exception as e:
                    print(f"Pocket TTS generation failed: {e}. Falling back to gTTS for this line.")
                    pocket_model = None # Force fallback for remaining lines

            if pocket_model is None:
                # Failover to gTTS!
                from gtts import gTTS
                gtts_lang = 'en'
                gtts_tld = 'com'
                
                # Check for accent tags
                if '-' in current_voice:
                    parts = current_voice.split('-')
                    gtts_lang = parts[0]
                    if parts[1] == 'uk' or parts[1] == 'gb':
                        gtts_tld = 'co.uk'
                    elif parts[1] == 'au':
                        gtts_tld = 'com.au'
                    elif parts[1] == 'ca':
                        gtts_tld = 'ca'
                    elif parts[1] == 'in':
                        gtts_tld = 'co.in'
                elif current_voice in ['es', 'fr', 'de', 'it']:
                    gtts_lang = current_voice
                else:
                    # Fallback mapping for Kyutai names if used in pocket-tts failover
                    mapping = {
                        "alba": ("it", "it"),
                        "marius": ("en", "co.uk"),
                        "javert": ("en", "com.au"),
                        "jean": ("fr", "fr"),
                        "fantine": ("fr", "fr"),
                        "cosette": ("fr", "fr"),
                        "eponine": ("fr", "fr"),
                        "azelma": ("fr", "fr")
                    }
                    if current_voice in mapping:
                        gtts_lang, gtts_tld = mapping[current_voice]
                    else:
                        gtts_lang, gtts_tld = ('en', 'com')

                try:
                    tts = gTTS(text=text, lang=gtts_lang, tld=gtts_tld)
                    mp3_buffer = io.BytesIO()
                    tts.write_to_fp(mp3_buffer)
                    mp3_buffer.seek(0)
                    line_segment = AudioSegment.from_file(mp3_buffer, format="mp3")
                except Exception as ex:
                    print(f"gTTS fallback failed: {ex}. Using robotic beep fallback.")
                    sample_rate = 24000
                    duration = max(0.2, len(text) * 0.04) # 40ms per character
                    freq = 200 + (ord(speaker[0]) % 10) * 40
                    t = np.linspace(0, duration, int(sample_rate * duration), False)
                    beep = np.sin(2 * np.pi * freq * t) * np.sin(np.pi * t / duration)
                    beep = (beep * 32767).astype(np.int16)
                    wav_buffer = io.BytesIO()
                    sf.write(wav_buffer, beep, sample_rate, format='WAV')
                    wav_buffer.seek(0)
                    line_segment = AudioSegment.from_wav(wav_buffer)

        elif model_name == "gemini-flash-tts":
            # Gemini Synthesis
            try:
                prompt = f"Please read the following text aloud with a clear, professional, natural voice. Do not add any introductory or concluding text, only say the words in the text itself. Text:\n{text}"
                response = client.models.generate_content(
                    model=os.environ.get("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview"),
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=current_voice
                                )
                            )
                        )
                    )
                )
                
                audio_bytes = None
                mime_type = None
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("audio/"):
                        audio_bytes = part.inline_data.data
                        mime_type = part.inline_data.mime_type
                        break
                        
                if not audio_bytes and hasattr(response, 'data') and response.data:
                    audio_bytes = response.data
                    
                if audio_bytes:
                    if isinstance(audio_bytes, str):
                        import base64
                        audio_bytes = base64.b64decode(audio_bytes)
                        
                    # Handle raw linear PCM (L16) data
                    if mime_type and ("l16" in mime_type.lower() or "pcm" in mime_type.lower()):
                        # Parse sample rate and channels from mime type, defaulting to 24000 and 1
                        rate = 24000
                        channels = 1
                        if "rate=" in mime_type.lower():
                            try:
                                rate = int(mime_type.lower().split("rate=")[1].split(";")[0])
                            except Exception:
                                pass
                        if "channels=" in mime_type.lower():
                            try:
                                channels = int(mime_type.lower().split("channels=")[1].split(";")[0])
                            except Exception:
                                pass
                        
                        line_segment = AudioSegment(
                            data=audio_bytes,
                            sample_width=2, # 16-bit
                            frame_rate=rate,
                            channels=channels
                        )
                    else:
                        line_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
                else:
                    print(f"Warning: No audio bytes returned in Gemini response for line {i+1}")
            except Exception as e:
                print(f"Gemini-Flash-TTS call failed: {e}. Using robotic beep fallback.")
                sample_rate = 24000
                duration = max(0.2, len(text) * 0.04)
                freq = 250 + (ord(speaker[0]) % 10) * 40
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                beep = np.sin(2 * np.pi * freq * t) * np.sin(np.pi * t / duration)
                beep = (beep * 32767).astype(np.int16)
                wav_buffer = io.BytesIO()
                sf.write(wav_buffer, beep, sample_rate, format='WAV')
                wav_buffer.seek(0)
                line_segment = AudioSegment.from_wav(wav_buffer)

        # Apply speed adjustment if speed != 1.0
        if line_segment is not None:
            if speed != 1.0:
                try:
                    from pydub.effects import speedup
                    line_segment = speedup(line_segment, playback_speed=speed)
                except Exception as e:
                    print(f"Warning: Failed to speed up line: {e}")
            
            final_audio += line_segment
            final_audio += AudioSegment.silent(duration=500)

    # Export final concatenated audio to disk
    if progress_queue:
        progress_queue.put({"type": "progress", "status": "Compiling final podcast file..."})
    final_audio.export(file_path, format="wav")
    print(f"Concatenated audio successfully written to {file_path}")
    if progress_queue:
        progress_queue.put({"type": "done"})

class AudioGenerationRequest(BaseModel):
    model_name: str = "kokoro-82m"
    settings: Optional[dict] = None

class AudioGenerationResponse(BaseModel):
    audio_id: int
    file_path: str
    download_url: str
    model_name: str
    settings: Optional[dict] = None

@router.post("/scripts/{script_id}/generate-audio")
async def generate_audio(script_id: int, request: Optional[AudioGenerationRequest] = None, db: AsyncSession = Depends(get_db)):
    if request is None:
        request = AudioGenerationRequest()

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

    # 3. Setup output file path with a unique timestamp
    import time
    import queue
    from utils.sse import format_sse
    from fastapi.responses import StreamingResponse

    output_dir = "audio_outputs"
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"script_{script_id}_{int(time.time())}.wav")

    model_name = request.model_name
    settings = request.settings or {}

    async def event_generator():
        progress_queue = queue.Queue()
        
        # Start synthesis in background thread executor
        loop = asyncio.get_running_loop()
        synthesis_task = loop.run_in_executor(
            None,
            _synthesize_audio_thread,
            lines,
            p_names,
            file_path,
            model_name,
            settings,
            progress_queue
        )
        
        # Stream updates from the queue
        while not synthesis_task.done() or not progress_queue.empty():
            try:
                item = progress_queue.get_nowait()
                if item["type"] == "progress":
                    yield format_sse({"status": item["status"]})
                elif item["type"] == "error":
                    yield format_sse({"status": f"[ERROR] Synthesis failed: {item['error']}"})
                    raise Exception(item["error"])
            except queue.Empty:
                await asyncio.sleep(0.05)

            # Cooperative yield for async runtime
            await asyncio.sleep(0.01)

        # Wait/retrieve exceptions
        try:
            await synthesis_task
        except Exception as e:
            yield format_sse({"status": f"[ERROR] Synthesis exception: {str(e)}"})
            return

        # 6. Always save a new Audio record in DB
        db_audio = models.Audio(
            script_id=script_id,
            file_path=file_path,
            model_name=model_name,
            settings=settings
        )
        db.add(db_audio)
        
        await db.commit()
        await db.refresh(db_audio)

        download_url = f"/projects/audio/{db_audio.id}"

        # Yield completion payload
        yield format_sse({
            "done": True,
            "id": db_audio.id,
            "audio_id": db_audio.id,
            "file_path": file_path,
            "download_url": download_url,
            "model_name": db_audio.model_name,
            "settings": db_audio.settings
        })

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/audio/{audio_id}")
async def get_audio_file(audio_id: int, db: AsyncSession = Depends(get_db)):
    db_audio = await db.get(models.Audio, audio_id)
    if not db_audio:
        raise HTTPException(status_code=404, detail="Audio record not found")

    if not os.path.exists(db_audio.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    return FileResponse(db_audio.file_path, media_type="audio/wav", filename=f"podcast_{audio_id}.wav")

@router.delete("/audio/{audio_id}")
async def delete_audio_file(audio_id: int, db: AsyncSession = Depends(get_db)):
    db_audio = await db.get(models.Audio, audio_id)
    if not db_audio:
        raise HTTPException(status_code=404, detail="Audio record not found")

    # Delete file from disk if it exists
    if os.path.exists(db_audio.file_path):
        try:
            os.remove(db_audio.file_path)
        except Exception as e:
            print(f"Failed to delete file {db_audio.file_path}: {e}")

    await db.delete(db_audio)
    await db.commit()
    return {"status": "success", "message": "Audio record deleted successfully"}
