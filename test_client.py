import httpx
import sys

def test_generate():
    url = "http://localhost:8000/generate"
    
    # Test transcript
    transcript = (
        "Hello! This is a test of the Kokoro 82M text to speech model running on FastAPI. "
        "It sounds surprisingly good for such a lightweight model, doesn't it?"
    )
    
    payload = {
        "text": transcript,
        "voice": "af_heart",  # American Female 'Heart'
        "speed": 1.0,
        "lang": "a"
    }
    
    print(f"Sending request to {url}...")
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload)
            
        if response.status_code == 200:
            output_file = "output.wav"
            with open(output_file, "wb") as f:
                f.write(response.content)
            print(f"Success! Audio saved to {output_file}")
        else:
            print(f"Failed! Status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_generate()
