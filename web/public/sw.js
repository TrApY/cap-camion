// Service worker de CAP Camión.
// Estrategia:
//  - Precache del app shell (rutas de la app, manifest, iconos) en install.
//  - _next/static (hasheado, inmutable): cache-first.
//  - Resto de GET same-origin (documentos, payloads RSC): stale-while-revalidate.
//  - Cross-origin (API de Supabase): se deja pasar a red; el banco se cachea
//    aparte en IndexedDB desde la app, así el examen funciona offline.
//
// Subir CACHE_VERSION invalida las cachés antiguas.
const CACHE_VERSION = "v2";
const CACHE = `cap-camion-${CACHE_VERSION}`;

const PRECACHE_URLS = [
  "/",
  "/examen",
  "/temas",
  "/estadisticas",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-maskable-512.png",
  "/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      // addAll falla si algún recurso no responde 200; lo hacemos tolerante.
      await Promise.allSettled(
        PRECACHE_URLS.map((url) =>
          fetch(url, { cache: "no-cache" })
            .then((res) => (res.ok ? cache.put(url, res) : null))
            .catch(() => null),
        ),
      );
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Solo gestionamos same-origin. Supabase y otros pasan directos a red.
  if (url.origin !== self.location.origin) return;

  // Activos estáticos inmutables: cache-first.
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(cacheFirst(req));
    return;
  }

  // Documentos y demás GET same-origin: stale-while-revalidate.
  event.respondWith(staleWhileRevalidate(req));
});

async function cacheFirst(req) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(req);
  if (cached) return cached;
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    return cached || Response.error();
  }
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(req);

  const network = fetch(req)
    .then((res) => {
      if (res.ok) cache.put(req, res.clone());
      return res;
    })
    .catch(() => null);

  if (cached) {
    // Refresca en segundo plano y responde ya con la copia cacheada.
    event_noop(network);
    return cached;
  }

  const res = await network;
  if (res) return res;

  // Sin red y sin caché: para navegaciones, cae a la home cacheada.
  if (req.mode === "navigate") {
    const home = await cache.match("/");
    if (home) return home;
  }
  return Response.error();
}

// Evita warnings de promesa flotante sin bloquear la respuesta.
function event_noop(p) {
  p.then(
    () => {},
    () => {},
  );
}
