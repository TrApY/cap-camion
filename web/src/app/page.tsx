import Link from "next/link";
import { TruckLogo } from "@/components/TruckLogo";

export default function Home() {
  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col items-center gap-3 pt-4 text-center">
        <TruckLogo className="h-20 w-20 rounded-2xl shadow-sm" />
        <h1 className="text-2xl font-extrabold tracking-tight">CAP Camión</h1>
        <p className="text-balance text-muted">
          Prepárate el{" "}
          <strong className="text-foreground">CAP de mercancías</strong> con
          exámenes simulados a partir de preguntas de exámenes oficiales reales.
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Cómo funciona
        </h2>
        <ul className="mt-3 space-y-2 text-sm leading-relaxed">
          <li className="flex gap-2">
            <span aria-hidden className="text-brand">
              •
            </span>
            <span>
              Banco con más de 2.500 preguntas recopiladas de exámenes
              oficiales.
            </span>
          </li>
          <li className="flex gap-2">
            <span aria-hidden className="text-brand">
              •
            </span>
            <span>
              El <strong>modo alta probabilidad</strong> prioriza las preguntas
              que más se repiten en los exámenes.
            </span>
          </li>
          <li className="flex gap-2">
            <span aria-hidden className="text-brand">
              •
            </span>
            <span>
              Funciona sin conexión: el banco se descarga una vez y se guarda en
              el móvil.
            </span>
          </li>
        </ul>
      </section>

      <nav className="flex flex-col gap-3">
        <Link
          href="/examen"
          className="flex items-center justify-center rounded-xl bg-brand px-5 py-4 text-center text-base font-semibold text-white shadow-sm transition hover:bg-brand-strong active:scale-[0.99]"
        >
          Examen simulado
        </Link>

        <Link
          href="/temas"
          className="flex items-center justify-center rounded-xl border border-border bg-surface px-5 py-4 text-center text-base font-semibold text-foreground shadow-sm transition hover:border-brand active:scale-[0.99]"
        >
          Práctica por temas
        </Link>

        <Link
          href="/repaso"
          className="flex items-center justify-center rounded-xl border border-border bg-surface px-5 py-4 text-center text-base font-semibold text-foreground shadow-sm transition hover:border-brand active:scale-[0.99]"
        >
          Repasar mis falladas
        </Link>

        <Link
          href="/estadisticas"
          className="flex items-center justify-center rounded-xl border border-border bg-surface px-5 py-4 text-center text-base font-semibold text-foreground shadow-sm transition hover:border-brand active:scale-[0.99]"
        >
          Mi progreso
        </Link>
      </nav>

      <p className="text-center text-xs leading-relaxed text-muted">
        Corrección con el baremo oficial del CAP (acierto +1, fallo −0,5, en
        blanco 0; aprobado ≥ 50/100). Exámenes públicos oficiales reproducidos
        para estudio.
      </p>
    </div>
  );
}
