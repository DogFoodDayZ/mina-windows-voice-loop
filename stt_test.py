import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

sr = 16000
seconds = 6

print("Recording now...")
audio = sd.rec(int(seconds * sr), samplerate=sr, channels=1, dtype="float32")
sd.wait()
sf.write("mic.wav", audio, sr)

print("Transcribing...")
model = WhisperModel("base.en", device="cpu", compute_type="int8")
segments, _ = model.transcribe("mic.wav", vad_filter=False, language="en")
text = " ".join(s.text.strip() for s in segments if s.text.strip())

print("Heard:", text if text else "(nothing)")