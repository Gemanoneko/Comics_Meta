"""Atomic JSON replacement with short Windows reader-lock retries."""
import json
import time
import uuid
from pathlib import Path

def save(path,value):
    path=Path(path)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        for attempt in range(20):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt==19:raise
                time.sleep(.05)
    finally:
        if temporary.exists():temporary.unlink()
