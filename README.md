# SpeakGenie – Real-Time AI Voice Tutor

**Stack**: Next.js (UI) • FastAPI (API) • Groq (STT + LLM) • gTTS (TTS, free)

## Features
- 🎙️ Voice → Text (Groq Whisper v3 Turbo)
- 🤖 Kid-safe Tutor (Groq Llama 3.1 8B Instant)
- 🔈 Text → Speech (MP3 via gTTS; plays ~1.1× speed in browser)
- 🎭 Roleplay: Tutor / School / Store / Home
- ⚠️ Safety: gentle refusals + short, simple language (6–16 yrs)

## Quick Start (Windows)

### 0) Prereqs
- Python 3.10+ • Node.js LTS • FFmpeg (installed via winget)
- Groq API key

### 1) Clone & env
