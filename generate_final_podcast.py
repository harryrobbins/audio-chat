import httpx
import json
import os
import io
from pydub import AudioSegment

def generate_podcast():
    base_url = "http://localhost:8000"
    input_file = "sample-text-palestine-records.md"
    
    with open(input_file, "r") as f:
        input_text = f.read()
    
    print("Step 1: Extracting facts...")
    with httpx.Client(timeout=120.0) as client:
        response = client.post(f"{base_url}/podcast/extract-facts", json={"text": input_text})
        response.raise_for_status()
        facts = response.json()
    
    print("Step 2: Generating script...")
    with httpx.Client(timeout=300.0) as client:
        response = client.post(f"{base_url}/podcast/generate-script", json={"facts": facts, "max_loops": 3})
        response.raise_for_status()
        result = response.json()
    
    personas = result["personas"]["personas"]
    script = result["script"]
    
    print(f"Title: {script['title']}")
    
    # Map personas to voices
    # Use a dictionary for lookup, but fallback to index-based if name doesn't match
    p_names = [p["name"] for p in personas]
    
    final_audio = AudioSegment.empty()
    
    print("Step 3: Generating audio for each line...")
    with httpx.Client(timeout=60.0) as client:
        for i, line in enumerate(script["lines"]):
            speaker = line["speaker"]
            text = line["text"]
            
            # Decide voice: if speaker name matches first persona, use heart, else michael
            if speaker == p_names[0]:
                voice = "af_heart"
            elif len(p_names) > 1 and speaker == p_names[1]:
                voice = "am_michael"
            else:
                # Fallback based on index parity if speaker name is unknown
                voice = "af_heart" if i % 2 == 0 else "am_michael"
            
            print(f"[{i+1}/{len(script['lines'])}] {speaker} ({voice}): {text[:50]}...")
            
            audio_response = client.post(f"{base_url}/generate", json={
                "text": text,
                "voice": voice,
                "speed": 1.0,
                "lang": "a"
            })
            audio_response.raise_for_status()
            
            # Load segment into pydub
            segment = AudioSegment.from_wav(io.BytesIO(audio_response.content))
            final_audio += segment
            
            # Add a small silence between lines
            final_audio += AudioSegment.silent(duration=500)
    
    output_file = "podcast_output.wav"
    final_audio.export(output_file, format="wav")
    print(f"\nSuccess! Final podcast saved to {output_file}")

if __name__ == "__main__":
    generate_podcast()
