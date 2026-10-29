// Display helpers shared by the live claim panel and the dashboard.

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

export const label = (s: string) => s.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());

export const VERDICT = {
  claim: { label: "Worth claiming", tone: "border-emerald-200 bg-emerald-50 text-emerald-900", dot: "bg-emerald-500" },
  dont_claim: { label: "Better not to claim", tone: "border-amber-200 bg-amber-50 text-amber-900", dot: "bg-amber-500" },
  borderline: { label: "Borderline", tone: "border-yellow-200 bg-yellow-50 text-yellow-900", dot: "bg-yellow-500" },
  not_covered: { label: "Not covered", tone: "border-red-200 bg-red-50 text-red-900", dot: "bg-red-500" },
};
