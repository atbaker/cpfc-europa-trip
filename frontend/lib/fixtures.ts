export type FixtureOption = {
  id: string;
  opponent: string;
  destination: string;
  date: string;
  kickoff: string;
};

// Mirrored from the reviewed backend catalog so the exported home page is immediately useful.
export const FIXTURES: readonly FixtureOption[] = [
  {
    id: "uel-2026-lyon-away",
    opponent: "Lyon",
    destination: "Lyon, France",
    date: "Thu 15 Oct",
    kickoff: "18:45 local",
  },
  {
    id: "uel-2026-besiktas-away",
    opponent: "Beşiktaş",
    destination: "Istanbul, Türkiye",
    date: "Thu 22 Oct",
    kickoff: "22:00 local",
  },
  {
    id: "uel-2026-jagiellonia-away",
    opponent: "Jagiellonia Białystok",
    destination: "Białystok, Poland",
    date: "Thu 10 Dec",
    kickoff: "18:45 local",
  },
  {
    id: "uel-2026-salzburg-away",
    opponent: "Salzburg",
    destination: "Salzburg, Austria",
    date: "Thu 28 Jan",
    kickoff: "21:00 local",
  },
] as const;

