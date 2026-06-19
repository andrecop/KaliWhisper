import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
from faster_whisper import WhisperModel

model_dir = os.path.join(os.path.dirname(__file__), "models")
models = ["tiny", "base", "small", "medium"]

for m in models:
    print(f"Scaricamento modello: {m}...")
    WhisperModel(m, device="cpu", compute_type="int8", download_root=model_dir)
    print(f"Modello {m} completato.")
