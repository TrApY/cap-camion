// Genera el identificador de build que usa el aviso de versión nueva (CAP-13).
// Escribe el MISMO id en dos sitios:
//   - src/lib/version.ts  → entra en el bundle: la versión que corre el cliente.
//   - public/version.json → lo sirve el servidor: la versión desplegada ahora.
// Si difieren, el cliente está usando una copia stale y se le ofrece recargar.
// Ambos ficheros están en .gitignore: se regeneran en cada `dev` y cada `build`.

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..");

/** Id corto, creciente en el tiempo y sin colisiones prácticas entre deploys. */
function nuevaVersion() {
  const azar = Math.random().toString(36).slice(2, 6).padEnd(4, "0");
  return `${Date.now().toString(36)}${azar}`;
}

const version = nuevaVersion();

mkdirSync(join(RAIZ, "src", "lib"), { recursive: true });
writeFileSync(
  join(RAIZ, "src", "lib", "version.ts"),
  `/** Generado por scripts/gen-version.mjs — no editar ni commitear. */\nexport const BUILD_VERSION = "${version}";\n`,
);

mkdirSync(join(RAIZ, "public"), { recursive: true });
writeFileSync(join(RAIZ, "public", "version.json"), `{"version":"${version}"}\n`);

console.log(`[gen-version] BUILD_VERSION=${version}`);
