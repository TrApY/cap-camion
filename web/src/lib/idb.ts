// Envoltura mínima sobre IndexedDB para el estado local de la app.
// Se usa IndexedDB en vez de localStorage porque el banco (~2 MB) puede rozar el
// límite de localStorage en algunos navegadores.
//
// Stores:
//  - "kv"       : clave-valor sin keyPath (caché del banco).
//  - "sesiones" : histórico de tests terminados (clave autoincremental).
//  - "progreso" : agregado por pregunta (keyPath "preguntaId").

const DB_NAME = "cap-camion";
// v2: se añaden las stores "sesiones" y "progreso" (estadísticas del usuario).
const DB_VERSION = 2;
const STORE = "kv";

/** Store con el histórico de tests terminados. */
export const STORE_SESIONES = "sesiones";
/** Store con el agregado de aciertos/fallos por pregunta. */
export const STORE_PROGRESO = "progreso";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB no disponible en este entorno."));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      // Se crean solo las stores que falten: así la subida de versión no
      // destruye la caché del banco ya descargada.
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
      if (!db.objectStoreNames.contains(STORE_SESIONES)) {
        db.createObjectStore(STORE_SESIONES, { autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(STORE_PROGRESO)) {
        db.createObjectStore(STORE_PROGRESO, { keyPath: "preguntaId" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function idbGet<T>(key: string): Promise<T | undefined> {
  const db = await openDb();
  try {
    return await new Promise<T | undefined>((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(key);
      req.onsuccess = () => resolve(req.result as T | undefined);
      req.onerror = () => reject(req.error);
    });
  } finally {
    db.close();
  }
}

export async function idbSet<T>(key: string, value: T): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(value, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

/** Devuelve todos los registros de una store. */
export async function idbGetAll<T>(store: string): Promise<T[]> {
  const db = await openDb();
  try {
    return await new Promise<T[]>((resolve, reject) => {
      const tx = db.transaction(store, "readonly");
      const req = tx.objectStore(store).getAll();
      req.onsuccess = () => resolve((req.result ?? []) as T[]);
      req.onerror = () => reject(req.error);
    });
  } finally {
    db.close();
  }
}

/** Inserta o reemplaza un registro en una store con keyPath. */
export async function idbPutIn<T>(store: string, value: T): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).put(value);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

/** Añade un registro a una store con clave autoincremental. */
export async function idbAddIn<T>(store: string, value: T): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).add(value);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

/** Vacía una store por completo. */
export async function idbClearStore(store: string): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).clear();
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

/**
 * Lee y reescribe varios registros de una store con keyPath en UNA sola
 * transacción readwrite (evita condiciones de carrera al aplicar deltas).
 * `actualizar` recibe el registro previo (o undefined si no existía) y devuelve
 * el nuevo valor; si devuelve `undefined` el registro se deja intacto.
 */
export async function idbActualizarVarios<T>(
  store: string,
  claves: string[],
  actualizar: (previo: T | undefined, clave: string) => T | undefined,
): Promise<void> {
  if (claves.length === 0) return;
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(store, "readwrite");
      const objectStore = tx.objectStore(store);
      for (const clave of claves) {
        const req = objectStore.get(clave);
        req.onsuccess = () => {
          const nuevo = actualizar(req.result as T | undefined, clave);
          if (nuevo !== undefined) objectStore.put(nuevo);
        };
      }
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}
