// Offline support: app shell + tour data cache-first (refreshed in background); Leaflet cached on first use.
const CACHE="walknyc-v6";
const SHELL=["./","index.html","tours.json","manifest.webmanifest","icon.svg","icon-180.png","icon-192.png"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()));});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener("fetch",e=>{
  const u=new URL(e.request.url);
  if(e.request.method!=="GET")return;
  const sameOrigin=u.origin===location.origin, leaflet=u.hostname==="unpkg.com";
  if(!sameOrigin&&!leaflet)return; // map tiles etc. go straight to network
  if(sameOrigin&&(u.pathname.includes("/audio/")||u.pathname.includes("/api/")))return; // audio streams with range requests; api is live data
  e.respondWith(caches.open(CACHE).then(async c=>{
    const hit=await c.match(e.request,{ignoreSearch:sameOrigin});
    const net=fetch(e.request).then(r=>{if(r.ok)c.put(e.request,r.clone());return r;}).catch(()=>hit);
    return hit||net;
  }));
});
