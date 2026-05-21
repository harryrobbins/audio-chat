import httpx
import json
import time

def test_podcast_flow():
    base_url = "http://localhost:8000/podcast"
    
    # Sample input text (a brief explanation of something)
    input_text = """
    The James Webb Space Telescope (JWST) is the most powerful space telescope ever built. 
    It is designed to look back in time to the very first galaxies that formed after the Big Bang.
    JWST orbits the sun at the second Lagrange point (L2), about 1.5 million kilometers from Earth.
    Unlike Hubble, which primarily looks at visible light, Webb focuses on the infrared spectrum.
    This allows it to see through dense clouds of dust that obscure stars and planets in visible light.
    """
    
    # Step 1: Extract Facts
    print("Step 1: Extracting facts...")
    with httpx.Client(timeout=60.0) as client:
        response = client.post(f"{base_url}/extract-facts", json={"text": input_text})
        
    if response.status_code != 200:
        print(f"Extraction failed: {response.text}")
        return
    
    facts = response.json()
    print("\nExtracted Facts:")
    print(json.dumps(facts, indent=2))
    
    # Step 2: Generate Script
    print("\nStep 2: Generating podcast script (this involves multiple agent loops)...")
    with httpx.Client(timeout=300.0) as client:
        response = client.post(
            f"{base_url}/generate-script", 
            json={"facts": facts, "max_loops": 3}
        )
        
    if response.status_code != 200:
        print(f"Script generation failed: {response.text}")
        return
    
    result = response.json()
    
    print("\n--- Generated Personas ---")
    print(json.dumps(result["personas"], indent=2))
    
    print("\n--- Final Podcast Script ---")
    script = result["script"]
    print(f"Title: {script['title']}")
    for line in script["lines"]:
        print(f"{line['speaker']}: {line['text']}")

if __name__ == "__main__":
    test_podcast_flow()
