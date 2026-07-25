import type { Metadata } from "next";
import { RankingClient } from "./RankingClient";

export const metadata: Metadata = {
  title: "Ranking",
};

export default function RankingPage() {
  return <RankingClient />;
}
