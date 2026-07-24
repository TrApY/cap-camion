import type { Metadata } from "next";
import { RepasoClient } from "./RepasoClient";

export const metadata: Metadata = {
  title: "Repaso de falladas",
};

export default function RepasoPage() {
  return <RepasoClient />;
}
