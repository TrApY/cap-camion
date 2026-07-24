import type { Metadata } from "next";
import { TemasClient } from "./TemasClient";

export const metadata: Metadata = {
  title: "Práctica por temas",
};

export default function TemasPage() {
  return <TemasClient />;
}
