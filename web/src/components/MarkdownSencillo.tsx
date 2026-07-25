// Pinta el markdown minimalista de lib/markdown.ts (párrafos, listas, negritas
// y subtítulos). Sin dependencias y sin HTML crudo: el texto siempre se muestra
// como texto.
import { parseMarkdownSencillo, type Fragmento } from "@/lib/markdown";

function Fragmentos({ contenido }: { contenido: Fragmento[] }) {
  return (
    <>
      {contenido.map((f, i) =>
        f.negrita ? (
          <strong key={i} className="font-semibold text-foreground">
            {f.texto}
          </strong>
        ) : (
          <span key={i}>{f.texto}</span>
        ),
      )}
    </>
  );
}

export function MarkdownSencillo({ md }: { md: string }) {
  const bloques = parseMarkdownSencillo(md);

  return (
    <div className="flex flex-col gap-3 text-sm leading-relaxed">
      {bloques.map((bloque, i) => {
        if (bloque.tipo === "subtitulo") {
          return (
            <h3 key={i} className="text-sm font-bold">
              <Fragmentos contenido={bloque.contenido} />
            </h3>
          );
        }
        if (bloque.tipo === "lista") {
          return (
            <ul key={i} className="flex flex-col gap-2">
              {bloque.items.map((item, j) => (
                <li key={j} className="flex gap-2">
                  <span aria-hidden className="flex-none text-brand">
                    •
                  </span>
                  <span>
                    <Fragmentos contenido={item} />
                  </span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i}>
            <Fragmentos contenido={bloque.contenido} />
          </p>
        );
      })}
    </div>
  );
}
