"""Build the app data from content/*.txt.

Writes hosting/cloudflare/public/tours.json (what the app loads) and voices/tracks.json
(what the audio render kit reads), then prints word counts and estimated durations.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent
tours = []
for f in sorted((ROOT / "content").glob("*.txt")):
    sections = re.split(r"^=== ", f.read_text(), flags=re.M)
    tour = None
    for sec in sections:
        if not sec.strip():
            continue
        head, _, body = sec.partition("\n")
        body = body.strip()
        if head.strip() == "TOUR":
            meta = dict(line.split(": ", 1) for line in body.splitlines() if ": " in line)
            tour = {k: meta[k] for k in ("id", "title", "area", "blurb")}
            tour["stops"] = []
        elif head.strip() == "OVERVIEW":
            tour["overview"] = body
        elif head.startswith("STOP "):
            m = re.match(r"STOP (.+?) @ (-?\d+\.\d+),(-?\d+\.\d+)$", head.strip())
            if not m:
                sys.exit(f"bad stop header in {f.name}: {head}")
            tour["stops"].append({"title": m[1], "lat": float(m[2]), "lng": float(m[3]), "text": body})
        else:
            sys.exit(f"unknown section {head!r} in {f.name}")
    tours.append(tour)

out = ROOT / "hosting" / "cloudflare" / "public" / "tours.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(tours, ensure_ascii=False, separators=(",", ":")))

tracks = []
for t in tours:
    tracks.append({"key": f"{t['id']}:-1", "file": f"{t['id']}-ov", "title": "Overview: " + t["title"], "text": t["overview"]})
    for i, s in enumerate(t["stops"]):
        tracks.append({"key": f"{t['id']}:{i}", "file": f"{t['id']}-{i + 1:02d}", "title": f"{i + 1}. {s['title']}", "text": s["text"]})
(ROOT / "voices" / "tracks.json").write_text(json.dumps(tracks, ensure_ascii=False, indent=0))

WPM = 165
total = 0
for t in tours:
    words = len(t["overview"].split()) + sum(len(s["text"].split()) for s in t["stops"])
    total += words
    print(f"{t['id']:26} {len(t['stops'])} stops {words:6} words {words / WPM:5.0f} min")
print(f"TOTAL {sum(len(t['stops']) for t in tours)} stops, {total} words, {total / WPM / 60:.1f} h at {WPM} wpm")
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
