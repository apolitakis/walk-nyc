"""Shared pieces for rendering Walk NYC narration to audio files.

Each engine script supplies one function, synth(text) -> (pcm_bytes, sample_rate),
that returns 16-bit mono PCM for a single sentence. This module splits tracks into
sentences, stitches the sentence audio together with short pauses, encodes the result,
and records when each sentence starts so the app can highlight and seek by sentence.
"""
import json, os, re, subprocess, sys, tempfile, wave
from pathlib import Path

HERE = Path(__file__).parent
SENTENCE_GAP = 0.28    # seconds of silence after each sentence
PARAGRAPH_GAP = 0.70   # seconds of silence after each paragraph
LEAD_IN = 0.30

# Same pronunciation fixes the app applies to on-device speech.
SPEAK_FIX = [
    (r"\bSt\. (?=[A-Z])", "Saint "), (r"\bAT&T\b", "A T and T"), (r"\bA&P\b", "A and P"), (r"&", " and "),
    (r"\b(East |West )?Houston Street", lambda m: (m.group(1) or "") + "Howston Street"),
    (r"Haughwout", "Howut"), (r"Spuyten Duyvil", "Spy-ten Dyvil"), (r"Loisaida", "Lo-ee-sigh-da"),
    (r"Nuyorican", "New-yo-rican"), (r"\bBC\b", "B.C."), (r"\bTKTS\b", "T K T S"), (r"\bBNY\b", "B N Y"),
    (r"\bCBGB\b", "C B G B"),
]

def to_speech(t):
    for pat, rep in SPEAK_FIX:
        t = re.sub(pat, rep, t)
    return t

_ABBR = re.compile(r"^(St|Mr|Mrs|Dr|Mt|Ft|vs|Co|No)\.$")
def split_sentences(par):
    """Port of the app's sentence splitter: never splits after initials or 'St.'."""
    out, start = [], 0
    for m in re.finditer(r"[.!?][\"”’']?(?=\s+[\"“‘']?[A-Z0-9])", par):
        end = m.end()
        seg = par[start:end]
        last = seg.split()[-1] if seg.split() else ""
        if _ABBR.match(last) or re.fullmatch(r"[A-Z]\.", last) or re.fullmatch(r"(?:[A-Z]\.){2,}", last):
            continue
        out.append(seg.strip()); start = end
    rest = par[start:].strip()
    if rest: out.append(rest)
    return out

def paragraphs(text):
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

def silence(sec, rate):
    return b"\x00\x00" * int(sec * rate)

def render_text(text, synth):
    """Returns (pcm, rate, sentences) where sentences = [[paragraph, start_sec, display_text], ...]."""
    pcm, rate, sents = bytearray(), None, []
    paras = paragraphs(text)
    for pi, p in enumerate(paras):
        ss = split_sentences(p)
        for si, s in enumerate(ss):
            audio, r = synth(to_speech(s))
            if rate is None:
                rate = r; pcm += silence(LEAD_IN, rate)
            sents.append([pi, round(len(pcm) / 2 / rate, 3), s])
            pcm += audio
            pcm += silence(PARAGRAPH_GAP if si == len(ss) - 1 and pi < len(paras) - 1 else SENTENCE_GAP, rate)
    return bytes(pcm), rate, sents

def write_wav(path, pcm, rate):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)

def encode(wav_path, out_path):
    """mp3 via ffmpeg where available, else AAC (.m4a) via macOS afconvert."""
    if out_path.suffix == ".mp3":
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-ac", "1", "-b:a", "64k", str(out_path)], check=True)
    else:
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "64000", str(wav_path), str(out_path)], check=True)

def pick_ext():
    from shutil import which
    if which("ffmpeg"): return ".mp3"
    if which("afconvert"): return ".m4a"
    sys.exit("Need ffmpeg (Linux: sudo apt install ffmpeg) or macOS afconvert to encode audio.")

def render_one(text, synth, out_path):
    pcm, rate, sents = render_text(text, synth)
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "t.wav"; write_wav(wav, pcm, rate); encode(wav, out_path)
    return round(len(pcm) / 2 / rate, 2), sents

def run_sample(engine, voices, synth_for_voice):
    ext = pick_ext(); out = HERE / "samples"; out.mkdir(exist_ok=True)
    text = (HERE / "sample.txt").read_text()
    for v in voices:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", v).strip("_")
        path = out / f"{engine}-{safe}{ext}"
        print(f"  {v} -> {path.name}", flush=True)
        try:
            render_one(text, synth_for_voice(v), path)
        except Exception as e:
            print(f"    failed: {e}")
    print(f"\nDone. Listen to the files in {out}")

def run_all(engine, voice_label, synth, limit=None):
    ext = pick_ext()
    out = HERE / "out" / "audio"; out.mkdir(parents=True, exist_ok=True)
    mpath = out / "manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {"tracks": {}}
    if manifest.get("voice") not in (None, f"{engine}:{voice_label}"):
        sys.exit(f"out/audio already holds a different voice ({manifest['voice']}). Move it aside first.")
    manifest["voice"] = f"{engine}:{voice_label}"
    tracks = json.loads((HERE / "tracks.json").read_text())[:limit]
    for n, t in enumerate(tracks, 1):
        fname = t["file"] + ext
        if t["key"] in manifest["tracks"] and (out / fname).exists():
            continue
        print(f"[{n}/{len(tracks)}] {t['title']}", flush=True)
        dur, sents = render_one(t["text"], synth, out / fname)
        manifest["tracks"][t["key"]] = {"file": "audio/" + fname, "dur": dur, "s": sents}
        mpath.write_text(json.dumps(manifest, ensure_ascii=False))  # save as we go, so a rerun resumes
    total = sum(v["dur"] for v in manifest["tracks"].values())
    print(f"\nDone: {len(manifest['tracks'])} tracks, {total/3600:.1f} hours of audio in {out}")
    print("Next: bash upload_r2.sh  (uploads to the walk-nyc-audio R2 bucket; see SHIPPING.md)")
