import os
import uuid
from pathlib import Path
from io import BytesIO

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq
from gtts import gTTS

# ===== Load env from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

API_BASE = "http://localhost:8000"
ROOT_DIR = Path(__file__).resolve().parents[1]
MEDIA_DIR = ROOT_DIR / "media"
STT_DIR = MEDIA_DIR / "stt"
TTS_DIR = MEDIA_DIR / "tts"
PROMPTS_DIR = ROOT_DIR / "server" / "prompts"
TUTOR_PROMPT_PATH = PROMPTS_DIR / "tutor_system.txt"

STT_DIR.mkdir(parents=True, exist_ok=True)
TTS_DIR.mkdir(parents=True, exist_ok=True)

# ===== Env
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    raise RuntimeError("Missing GROQ_API_KEY in .env")

STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3-turbo")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama-3.1-8b-instant")
CHAT_TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", "0.7"))
CHAT_MAX_TOKENS = int(os.getenv("CHAT_MAX_TOKENS", "200"))
TTS_RESPONSE_FORMAT = (os.getenv("TTS_RESPONSE_FORMAT", "mp3") or "mp3").lower()  # mp3 default

# ===== Clients
client = Groq(api_key=GROQ_API_KEY)

# ===== App
app = FastAPI(title="SpeakGenie Voice Tutor API")

# Allow Next.js dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== Models
class ChatIn(BaseModel):
    user_text: str
    scenario: str | None = None


# ===== Endpoints
@app.get("/health")
def health():
    return {
        "status": "ok",
        "env_loaded": bool(GROQ_API_KEY),
        "models": {
            "stt": STT_MODEL,
            "chat": CHAT_MODEL,
            "tts_format_default": TTS_RESPONSE_FORMAT,
        },
    }


@app.post("/stt")
async def stt(audio: UploadFile = File(...)):
    """
    Accepts a short audio clip (webm/mp3/m4a/wav) and returns text.
    """
    ext = (Path(audio.filename).suffix or ".webm").lower()
    if ext not in [".webm", ".mp3", ".m4a", ".wav"]:
        ext = ".webm"
    tmp_path = STT_DIR / f"{uuid.uuid4().hex}{ext}"

    try:
        data = await audio.read()
        if not data or len(data) < 10:
            raise HTTPException(status_code=422, detail="Empty audio upload")
        tmp_path.write_bytes(data)

        # Groq Whisper STT
        with open(tmp_path, "rb") as f:
            tr = client.audio.transcriptions.create(
                file=f,
                model=STT_MODEL,
            )

        text = getattr(tr, "text", None) or ""
        if not text.strip():
            raise HTTPException(status_code=422, detail="Empty transcription")

        return {"text": text.strip()}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT failed: {e}")
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


@app.post("/chat")
async def chat(body: ChatIn):
    """
    Accepts { user_text, scenario } and returns a short tutor reply via Groq LLM.
    """
    if not body.user_text or not body.user_text.strip():
        raise HTTPException(status_code=422, detail="user_text required")

    if not TUTOR_PROMPT_PATH.exists():
        raise HTTPException(status_code=500, detail="Tutor system prompt not found.")

    system_text = TUTOR_PROMPT_PATH.read_text(encoding="utf-8")

    # Append role scenario (optional)
    if body.scenario:
        system_text += (
            f"\n\nScenario: {body.scenario}\n"
            "Stay in character and use everyday, kid-friendly language."
        )

    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=CHAT_TEMPERATURE,
            max_tokens=CHAT_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": body.user_text.strip()},
            ],
        )
        reply = resp.choices[0].message.content.strip()
        if not reply:
            raise HTTPException(status_code=502, detail="Empty reply from model.")
        return {"reply": reply}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


@app.post("/tts")
async def tts(
    text: str = Form(...),
    voice: str | None = Form(None),   # kept for future providers; ignored by gTTS
    format: str | None = Form(None),  # we support mp3 only in this minimal build
):
    """
    Generates speech from text using free gTTS.
    - For simplicity & reliability on Windows/Python 3.13, we return MP3 only.
    """
    t = (text or "").strip()
    if not t:
        raise HTTPException(status_code=422, detail="text is required")

    # If caller sends format other than mp3, we still return mp3.
    try:
        mp3_bytes = BytesIO()
        gTTS(t, lang="en").write_to_fp(mp3_bytes)
        mp3_bytes.seek(0)
        return StreamingResponse(mp3_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {e}")
