"""Build the app data from content/*.txt and content/deeper/*.txt.

Writes hosting/cloudflare/public/tours.json (what the app loads) and voices/tracks.json
(what the audio render kit reads), then prints word counts and estimated durations.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent

# Topics a "Go deeper" chapter can be tagged with. The app's LENSES list (index.html) has the labels.
LENSES = ("history", "people", "companies", "architecture", "nature", "look",
          "underfoot", "names", "food", "politics", "culture", "legends")

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
    tour["file"] = f.name
    tours.append(tour)

# "Go deeper" chapters: content/deeper/<same name as the tour file>.txt
#   === STOP <stop title, exactly as in the tour file>
#   === DEEPER <chapter title> | <lens>
#   Paragraphs.
by_file = {t["file"]: t for t in tours}
for f in sorted((ROOT / "content" / "deeper").glob("*.txt")):
    tour = by_file.get(f.name)
    if not tour:
        sys.exit(f"content/deeper/{f.name} has no matching content/{f.name}")
    stops = {s["title"]: s for s in tour["stops"]}
    stop = None
    for sec in re.split(r"^=== ", f.read_text(), flags=re.M):
        if not sec.strip():
            continue
        head, _, body = sec.partition("\n")
        head, body = head.strip(), body.strip()
        if head.startswith("STOP "):
            stop = stops.get(head[5:].strip())
            if stop is None:
                sys.exit(f"deeper/{f.name}: no stop titled {head[5:].strip()!r} in {f.name}")
            if "deeper" in stop:
                sys.exit(f"deeper/{f.name}: stop {stop['title']!r} appears twice")
            stop["deeper"] = []
        elif head.startswith("DEEPER "):
            m = re.match(r"DEEPER (.+?)\s*\|\s*([a-z]+)$", head)
            if not m:
                sys.exit(f"deeper/{f.name}: bad chapter header {head!r} (want: DEEPER Title | lens)")
            if m[2] not in LENSES:
                sys.exit(f"deeper/{f.name}: unknown lens {m[2]!r} in {head!r}; use one of {', '.join(LENSES)}")
            if stop is None:
                sys.exit(f"deeper/{f.name}: chapter {m[1]!r} comes before any STOP line")
            if not body:
                sys.exit(f"deeper/{f.name}: chapter {m[1]!r} is empty")
            stop["deeper"].append({"title": m[1], "lens": m[2], "text": body})
        else:
            sys.exit(f"deeper/{f.name}: unknown section {head!r}")

for t in tours:
    del t["file"]

out = ROOT / "hosting" / "cloudflare" / "public" / "tours.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(tours, ensure_ascii=False, separators=(",", ":")))

# Track keys: "<tour>:-1" overview, "<tour>:<i>" stop i (0-based), "<tour>:<i>:<n>" its deeper chapter n (1-based).
tracks = []
for t in tours:
    tracks.append({"key": f"{t['id']}:-1", "file": f"{t['id']}-ov", "title": "Overview: " + t["title"], "text": t["overview"]})
    for i, s in enumerate(t["stops"]):
        tracks.append({"key": f"{t['id']}:{i}", "file": f"{t['id']}-{i + 1:02d}", "title": f"{i + 1}. {s['title']}", "text": s["text"]})
        for n, c in enumerate(s.get("deeper", []), 1):
            tracks.append({"key": f"{t['id']}:{i}:{n}", "file": f"{t['id']}-{i + 1:02d}-d{n}",
                           "title": f"{i + 1}. {s['title']} / deeper {n}: {c['title']}", "text": c["text"]})
(ROOT / "voices" / "tracks.json").write_text(json.dumps(tracks, ensure_ascii=False, indent=0))

WPM = 165
total = total_deep = stops_deep = chapters = 0
lens_count = {k: 0 for k in LENSES}
for t in tours:
    words = len(t["overview"].split()) + sum(len(s["text"].split()) for s in t["stops"])
    deep = sum(len(c["text"].split()) for s in t["stops"] for c in s.get("deeper", []))
    have = sum(1 for s in t["stops"] if s.get("deeper"))
    total += words; total_deep += deep; stops_deep += have
    for s in t["stops"]:
        for c in s.get("deeper", []):
            chapters += 1; lens_count[c["lens"]] += 1
    extra = f"   deeper: {have}/{len(t['stops'])} stops {deep:6} words {deep / WPM:4.0f} min" if have else ""
    print(f"{t['id']:26} {len(t['stops'])} stops {words:6} words {words / WPM:5.0f} min{extra}")
nstops = sum(len(t["stops"]) for t in tours)
print(f"TOTAL {nstops} stops, {total} words, {total / WPM / 60:.1f} h at {WPM} wpm")
print(f"DEEPER {stops_deep}/{nstops} stops, {chapters} chapters, {total_deep} words, {total_deep / WPM / 60:.1f} h"
      + ("   by lens: " + ", ".join(f"{k} {v}" for k, v in lens_count.items() if v) if chapters else ""))
print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
