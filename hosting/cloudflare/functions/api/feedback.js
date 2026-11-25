// Walk-time feedback notes.
//   POST /api/feedback  {note, tour, stop, stopTitle, deeper, chapterTitle, sentence, lat, lng, acc, app, at}  -> stores one note in KV
//   (deeper = the "Go deeper" chapter number, 1-based, when the note was written during a chapter)
//   GET  /api/feedback  with header "x-feedback-key: <FEEDBACK_KEY>" (or ?key=)  -> {notes:[...]} newest first
// Bindings (wrangler.toml / Pages settings): FEEDBACK = KV namespace; FEEDBACK_KEY = secret for reading.

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });
const str = (v, max) => (v == null ? null : String(v).slice(0, max));
const num = v => (typeof v === "number" && Number.isFinite(v) ? Math.round(v * 1e6) / 1e6 : null);

export async function onRequestPost({ request, env }) {
  if (!env.FEEDBACK) return json({ error: "feedback storage not configured" }, 503);
  let b;
  try { b = await request.json(); } catch { return json({ error: "bad json" }, 400); }
  const note = str(b.note, 4000);
  if (!note || !note.trim()) return json({ error: "empty note" }, 400);
  const at = new Date().toISOString();
  const entry = {
    id: crypto.randomUUID(), at, clientAt: str(b.at, 40), note: note.trim(),
    tour: str(b.tour, 64), stop: Number.isInteger(b.stop) ? b.stop : null, stopTitle: str(b.stopTitle, 200),
    deeper: Number.isInteger(b.deeper) ? b.deeper : null, chapterTitle: str(b.chapterTitle, 200),
    sentence: str(b.sentence, 1000), lat: num(b.lat), lng: num(b.lng), acc: num(b.acc),
    app: str(b.app, 32), ua: str(request.headers.get("user-agent"), 200),
  };
  // Key sorts newest-first: invert the timestamp so KV's ascending list returns recent notes first.
  const inv = String(9e15 - Date.now()).padStart(16, "0");
  await env.FEEDBACK.put(`note:${inv}:${entry.id}`, JSON.stringify(entry));
  return json({ ok: true, id: entry.id });
}

export async function onRequestGet({ request, env }) {
  const key = request.headers.get("x-feedback-key") || new URL(request.url).searchParams.get("key");
  if (!env.FEEDBACK_KEY || key !== env.FEEDBACK_KEY) return json({ error: "unauthorized" }, 401);
  if (!env.FEEDBACK) return json({ error: "feedback storage not configured" }, 503);
  const notes = [];
  let cursor;
  do {
    const page = await env.FEEDBACK.list({ prefix: "note:", cursor, limit: 1000 });
    const vals = await Promise.all(page.keys.map(k => env.FEEDBACK.get(k.name, "json")));
    notes.push(...vals.filter(Boolean));
    cursor = page.list_complete ? null : page.cursor;
  } while (cursor && notes.length < 5000);
  return json({ notes });
}
