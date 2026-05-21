import json
from typing import AsyncGenerator

def format_sse(data: dict, event: str = None) -> str:
    msg = f"data: {json.dumps(data)}\n\n"
    if event:
        msg = f"event: {event}\n" + msg
    return msg
