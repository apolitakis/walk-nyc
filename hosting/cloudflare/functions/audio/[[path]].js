// Serves recorded narration from the R2 bucket bound as AUDIO, at /audio/<file>.
// Supports HTTP Range requests: iPhone Safari streams and seeks media with them and won't play audio without them.
// Bucket layout: audio/manifest.json, audio/<tour>-ov.mp3, audio/<tour>-01.mp3, ...

const TYPES = { mp3: "audio/mpeg", m4a: "audio/mp4", json: "application/json" };

function parseRange(header, size) {
  const m = /^bytes=(\d*)-(\d*)$/.exec(header || "");
  if (!m || (m[1] === "" && m[2] === "")) return null;
  let start, end;
  if (m[1] === "") { start = Math.max(0, size - Number(m[2])); end = size - 1; }  // suffix: last N bytes
  else { start = Number(m[1]); end = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1); }
  if (start > end || start >= size) return "invalid";
  return { offset: start, length: end - start + 1 };
}

async function serve({ request, env, params }, headOnly) {
  if (!env.AUDIO) return new Response("Audio storage not configured", { status: 404 });
  const key = "audio/" + [].concat(params.path || []).join("/");
  const head = await env.AUDIO.head(key);
  if (!head) return new Response("Not found", { status: 404 });

  const headers = new Headers();
  head.writeHttpMetadata(headers);
  const ext = key.split(".").pop();
  if (!headers.get("content-type") && TYPES[ext]) headers.set("content-type", TYPES[ext]);
  headers.set("etag", head.httpEtag);
  headers.set("accept-ranges", "bytes");
  headers.set("cache-control", ext === "json" ? "no-cache" : "public, max-age=86400");

  const range = parseRange(request.headers.get("range"), head.size);
  if (range === "invalid") {
    headers.set("content-range", `bytes */${head.size}`);
    return new Response(null, { status: 416, headers });
  }
  if (range) {
    headers.set("content-range", `bytes ${range.offset}-${range.offset + range.length - 1}/${head.size}`);
    headers.set("content-length", String(range.length));
    if (headOnly) return new Response(null, { status: 206, headers });
    const obj = await env.AUDIO.get(key, { range });
    return new Response(obj.body, { status: 206, headers });
  }
  headers.set("content-length", String(head.size));
  if (headOnly) return new Response(null, { headers });
  const obj = await env.AUDIO.get(key);
  return new Response(obj.body, { headers });
}

export const onRequestGet = ctx => serve(ctx, false);
export const onRequestHead = ctx => serve(ctx, true);
