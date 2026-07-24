import type { Metadata } from "next";
import { ExamenClient } from "./ExamenClient";

export const metadata: Metadata = {
  title: "Examen simulado",
};

export default function ExamenPage() {
  return <ExamenClient />;
}
