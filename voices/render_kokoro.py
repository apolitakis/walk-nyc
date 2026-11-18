"""Render Walk NYC narration with Kokoro-82M (open-weights neural TTS, Apache-2.0).

  pip install "kokoro>=0.9" soundfile        (plus: sudo apt install espeak-ng ffmpeg)
  python3 render_kokoro.py --sample          # one ~75 s passage in 8 voices -> samples/
  python3 render_kokoro.py --all --voice af_heart     # everything -> out/audio/

First run downloads the model (~330 MB) from Hugging Face. Reruns resume where they stopped.
"""
import argparse, subprocess, sys
import common

SAMPLE_VOICES = ["af_heart", "af_bella", "af_nicole", "am_michael", "am_fenrir", "am_puck", "bf_emma", "bm_george"]

def gpu_fan_ok():
    try:
        return subprocess.run(["systemctl", "is-active", "gpu-fan"], capture_output=True, text=True).stdout.strip() == "active"
    except FileNotFoundError:
        return True  # not the lab box / no systemd: nothing to check

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--voice", default="af_heart")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--device", default=None, help="cuda or cpu (default: cuda if available)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N tracks (for a test run)")
    a = ap.parse_args()
    if not (a.sample or a.all): ap.error("pass --sample or --all")

    import numpy as np, torch
    from kokoro import KPipeline
    dev = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    if dev == "cuda" and not gpu_fan_ok():
        sys.exit("gpu-fan service is not active: refusing to load the GPU. Start it, or rerun with --device cpu.")
    print(f"Kokoro on {dev}")

    pipes = {}
    def pipe(lang):
        if lang not in pipes:
            try: pipes[lang] = KPipeline(lang_code=lang, device=dev)
            except TypeError: pipes[lang] = KPipeline(lang_code=lang)
        return pipes[lang]

    def synth_for_voice(voice):
        p = pipe(voice[0])  # 'a' = American English, 'b' = British English
        def synth(text):
            chunks = []
            for r in p(text, voice=voice, speed=a.speed):
                audio = r.audio if hasattr(r, "audio") else r[2]
                if audio is not None: chunks.append(audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio))
            x = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
            return (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes(), 24000
        return synth

    if a.sample:
        common.run_sample("kokoro", SAMPLE_VOICES, synth_for_voice)
    else:
        common.run_all("kokoro", a.voice, synth_for_voice(a.voice), a.limit)

if __name__ == "__main__":
    main()
