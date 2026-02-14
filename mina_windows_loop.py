"""
mina_windows_loop.py
Windows mic -> local STT (faster-whisper) -> WSL OpenClaw -> Windows TTS playback

Requirements (inside Windows venv):
  pip install sounddevice soundfile faster-whisper edge-tts

Notes:
- Uses WSL to call OpenClaw CLI.
- Locks to a specific Windows input device index (INPUT_DEVICE).
- Cleans reply text for smoother TTS playback.
"""

import json
import re
import subprocess
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

# =========================
# Core runtime config
# =========================
SR = 16000                 # sample rate for recording
SECONDS = 8                # mic capture length per turn
INPUT_DEVICE = 1           # your selected mic device index from sounddevice list
SESSION_ID = "voice-loop"  # OpenClaw conversation session id
VOICE = "en-US-AnaNeural"  # Edge TTS voice

# =========================
# WSL / OpenClaw bridge config
# =========================
WSL_DISTRO = "kali-linux"
WSL_USER = "travis"
OPENCLAW_MJS = "/home/travis/.npm-global/lib/node_modules/openclaw/openclaw.mjs"
NODE_WSL = "/home/linuxbrew/.linuxbrew/bin/node"


# =========================
# Text cleanup helpers
# =========================
def clean_text(text: str) -> str:
    """Remove reply tags/markdown-ish artifacts and normalize whitespace."""
    t = re.sub(r"\[\[\s*reply_to[^\]]*\]\]", "", text, flags=re.I)
    t = re.sub(r"[`*_#>~]", "", t)
    t = t.replace("\n", " ").replace("—", ", ").replace("–", ", ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def strip_emoji(text: str) -> str:
    """Drop supplementary-plane emoji to avoid mojibake in some terminals."""
    return re.sub(r"[\U00010000-\U0010ffff]", "", text)


# =========================
# WSL command execution
# =========================
def run_wsl_bash(command: str):
    """
    Run bash command in WSL with UTF-8 locale forced.
    This prevents cp1252 decode crashes on Windows.
    """
    command = f'export LANG=C.UTF-8 LC_ALL=C.UTF-8; {command}'
    cmd = ["wsl.exe", "-d", WSL_DISTRO, "-u", WSL_USER, "bash", "-lc", command]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False
    )


def ask_mina_via_wsl(message: str, session_id: str):
    """
    Call OpenClaw CLI inside WSL and return subprocess result.
    """
    quoted_msg = json.dumps(message)  # safe shell literal for message body
    cmd = (
        f'"{NODE_WSL}" "{OPENCLAW_MJS}" agent '
        f'--session-id {session_id} --message {quoted_msg} --json'
    )
    return run_wsl_bash(cmd)


# =========================
# Playback helper
# =========================
def play_audio_windows(path: str):
    """
    Play generated audio without blocking on GUI media app if ffplay is available.
    - Preferred: ffplay (no window/focus steal)
    - Fallback: default player via Start-Process
    """
    ff = subprocess.run(["where", "ffplay"], capture_output=True, text=True, shell=True)
    if ff.returncode == 0:
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", path], check=False)
    else:
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Start-Process '{path}'"], check=False)


# =========================
# STT helper
# =========================
def transcribe_audio(model: WhisperModel, wav_path: str) -> str:
    """
    Transcribe WAV with whisper model and return normalized text.
    beam_size=5 improves accuracy over greedy decode.
    """
    segments, _ = model.transcribe(
        wav_path,
        vad_filter=False,
        language="en",
        beam_size=5
    )
    text = " ".join(s.text.strip() for s in segments if s.text and s.text.strip()).strip()
    return clean_text(text)


# =========================
# Main loop
# =========================
def main():
    print("Loading STT model...")
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    print("Ready.")

    while True:
        try:
            input("\nPress Enter to speak (Ctrl+C to quit)... ")

            # 1) Record mic audio
            print(f"Recording {SECONDS}s...")
            audio = sd.rec(
                int(SECONDS * SR),
                samplerate=SR,
                channels=1,
                dtype="float32",
                device=INPUT_DEVICE
            )
            sd.wait()
            sf.write("mic.wav", audio, SR)

            # 2) Transcribe speech locally
            print("Transcribing...")
            text = transcribe_audio(model, "mic.wav")

            # Basic transcript quality gates
            if not text:
                print("Didn't catch that.")
                continue
            if not re.search(r"[a-zA-Z0-9]", text):
                print("Heard only noise/punctuation, skipping.")
                continue
            if len(text.split()) < 2:
                print(f"Too short, skipping: {text!r}")
                continue

            print("You:", text)

            # 3) Ask Mina via WSL OpenClaw
            print("Asking Mina via WSL...")
            proc = ask_mina_via_wsl(text, SESSION_ID)

            if proc.returncode != 0:
                print("WSL/OpenClaw failed:")
                print(proc.stderr[:1200] if proc.stderr else "(no stderr)")
                continue

            if not proc.stdout:
                print("No stdout from WSL OpenClaw call.")
                print("stderr:", proc.stderr[:1200] if proc.stderr else "(none)")
                continue

            # 4) Parse OpenClaw JSON reply
            try:
                data = json.loads(proc.stdout)
            except Exception:
                print("Could not parse JSON from WSL.")
                print("stdout:", proc.stdout[:1200])
                print("stderr:", proc.stderr[:1200] if proc.stderr else "(none)")
                continue

            payloads = ((data.get("result") or {}).get("payloads") or [])
            reply = next(
                ((p.get("text") or "").strip() for p in payloads if (p.get("text") or "").strip()),
                ""
            )
            if not reply:
                reply = "I heard you, but I don't have a reply yet."

            # 5) Clean output for terminal + TTS
            reply = strip_emoji(clean_text(reply))
            reply = reply.encode("ascii", "ignore").decode("ascii")
            print("Mina:", reply)

            # 6) Synthesize + play TTS
            spoken = reply[:500]
            subprocess.run(
                ["edge-tts", "--voice", VOICE, "--text", spoken, "--write-media", "reply.mp3"],
                check=False
            )
            play_audio_windows("reply.mp3")

        except EOFError:
            print("\nInput stream closed. Exiting.")
            break
        except KeyboardInterrupt:
            print("\nBye.")
            break
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")
            continue


if __name__ == "__main__":
    main()