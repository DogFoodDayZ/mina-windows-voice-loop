# Mina Windows Voice Loop

Windows-native mic + TTS loop for OpenClaw running in WSL.

This script records your voice on Windows, transcribes with `faster-whisper`, sends text to OpenClaw in WSL, then speaks the response with Edge TTS.

## Quickstart

```powershell
cd C:\Users\Admin\mina-voice
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python .\mina_windows_loop.py
Features
Windows-native audio I/O (no WSL audio bridge)
Local speech-to-text via faster-whisper
OpenClaw query over WSL command bridge
Edge TTS voice output (default: en-US-AnaNeural)
Cleans noisy output (emoji stripping, text cleanup)
