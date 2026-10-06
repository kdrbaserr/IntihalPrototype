export type Evidence = {
  char_start: number; char_end: number; text: string; page_number: number | null;
};
export type MatchEvidence = {
  id: string; similarity_score: string | number;
  document: Evidence;
  source: Evidence & { source_document_id: string; title: string; source_url: string | null };
};
export type MergedRange = {
  start: number; end: number; text: string; score: number;
  pages: (number | null)[]; matches: MatchEvidence[];
};

export function scoreLevel(score: number): "low" | "medium" | "high" {
  return score >= 0.8 ? "high" : score >= 0.5 ? "medium" : "low";
}

export const SCORE_LABELS = { low: "Düşük", medium: "Orta", high: "Yüksek" };

export function mergeMatchRanges(matches: MatchEvidence[]): MergedRange[] {
  const sorted = [...matches].sort((a, b) =>
    a.document.char_start - b.document.char_start || a.document.char_end - b.document.char_end);
  const groups: MergedRange[] = [];
  for (const match of sorted) {
    const { char_start: start, char_end: end, text, page_number: page } = match.document;
    const score = Number(match.similarity_score);
    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end <= start ||
        !Number.isFinite(score) || score < 0 || score > 1 || Array.from(text).length !== end - start) {
      throw new Error("Invalid match range");
    }
    const previous = groups.at(-1);
    if (!previous || start >= previous.end) {
      groups.push({ start, end, text, score, pages: [page], matches: [match] });
      continue;
    }
    const characters = Array.from(text);
    const overlap = Math.min(previous.end, end) - start;
    const existing = Array.from(previous.text).slice(start - previous.start, start - previous.start + overlap);
    if (existing.join("") !== characters.slice(0, overlap).join("")) {
      throw new Error("Inconsistent overlapping evidence");
    }
    previous.text += characters.slice(overlap).join("");
    previous.end = Math.max(previous.end, end);
    previous.score = Math.max(previous.score, score);
    if (!previous.pages.includes(page)) previous.pages.push(page);
    previous.matches.push(match);
  }
  return groups;
}
