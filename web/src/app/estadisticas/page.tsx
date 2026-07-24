import type { Metadata } from "next";
import { EstadisticasClient } from "./EstadisticasClient";

export const metadata: Metadata = {
  title: "Mi progreso",
};

export default function EstadisticasPage() {
  return <EstadisticasClient />;
}
