"""Render Walk NYC narration with macOS's built-in voices (including downloaded Premium ones).

No installs needed. Download voices first: System Settings > Accessibility > Spoken Content >
System voice > Manage Voices... > English, and tick the Premium/Enhanced voices you want.

  python3 render_mac.py --sample                  # sample passage in every Premium/Enhanced English voice -> samples/
  python3 render_mac.py --all --voice "Ava (Premium)"   # everything -> out/audio/
"""
import argparse, re, subprocess, sys, tempfile, wave
from pathlib import Path
import common

def installed_voices():
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    vs = []
    for line in out.splitlines():
        m = re.match(r"^(.+?)\s{2,}(\w\w[_-]\w+)\s", line)
        if m: vs.append((m.group(1).strip(), m.group(2)))
    return vs

def synth_for_voice(voice, rate=None):
    def synth(text):
        with tempfile.TemporaryDirectory() as d:
            src, wav = Path(d) / "t.txt", Path(d) / "t.wav"
            src.write_text(text)
            cmd = ["say", "-v", voice, "-f", str(src), "-o", str(wav), "--file-format=WAVE", "--data-format=LEI16@24000"]
            if rate: cmd += ["-r", str(rate)]
            subprocess.run(cmd, check=True)
            with wave.open(str(wav)) as w:
                return w.readframes(w.getnframes()), w.getframerate()
    return synth

def main():
    if sys.platform != "darwin": sys.exit("This script runs on a Mac.")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--voice", default="Ava (Premium)")
    ap.add_argument("--rate", type=int, default=None, help="words per minute (default: the voice's own)")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if not (a.sample or a.all): ap.error("pass --sample or --all")
    if a.sample:
        vs = [n for n, lang in installed_voices() if lang.startswith("en") and re.search(r"Premium|Enhanced", n)]
        if not vs: sys.exit("No Premium/Enhanced English voices installed. See the note at the top of this file.")
        common.run_sample("mac", vs, lambda v: synth_for_voice(v, a.rate))
    else:
        common.run_all("mac", a.voice, synth_for_voice(a.voice, a.rate), a.limit)

if __name__ == "__main__":
    main()
