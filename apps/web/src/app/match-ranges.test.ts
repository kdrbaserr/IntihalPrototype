import { describe, expect, it } from "vitest";
import { MatchEvidence, mergeMatchRanges, scoreLevel } from "./match-ranges";

export function evidence(id: string, start: number, end: number, score = 0.6, full = "abcdefghij"): MatchEvidence {
  const text = Array.from(full).slice(start, end).join("");
  return { id, similarity_score: String(score),
    document: { char_start: start, char_end: end, text, page_number: 1 },
    source: { char_start: 0, char_end: end - start, text, page_number: null,
      source_document_id: id, title: `Kaynak ${id}`, source_url: null } };
}

describe("mergeMatchRanges", () => {
  it("merges chained overlap, keeps source evidence and chooses the highest score", () => {
    const matches = [evidence("c", 6, 10, 0.4), evidence("b", 3, 8, 0.9), evidence("a", 0, 5, 0.6)];
    const original = structuredClone(matches);
    const groups = mergeMatchRanges(matches);
    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({ start: 0, end: 10, text: "abcdefghij", score: 0.9, pages: [1] });
    expect(groups[0].matches.map((match) => match.id)).toEqual(["a", "b", "c"]);
    expect(matches).toEqual(original);
  });
  it("keeps contained and identical evidence without duplicating text", () => {
    const groups = mergeMatchRanges([evidence("a", 0, 8), evidence("b", 2, 5), evidence("c", 0, 8)]);
    expect(groups[0].text).toBe("abcdefgh");
    expect(groups[0].matches).toHaveLength(3);
  });
  it("keeps touching and disjoint half-open intervals separate", () => {
    expect(mergeMatchRanges([evidence("a", 0, 3), evidence("b", 3, 5), evidence("c", 7, 10)])).toHaveLength(3);
    expect(mergeMatchRanges([])).toEqual([]);
  });
  it("uses Unicode code points and preserves page references", () => {
    const a = evidence("a", 0, 4, 0.5, "😀abcçdef");
    const b = evidence("b", 2, 7, 0.7, "😀abcçdef");
    b.document.page_number = 2;
    const [group] = mergeMatchRanges([b, a]);
    expect(group.text).toBe("😀abcçde");
    expect(group.pages).toEqual([1, 2]);
  });
  it("rejects malformed or inconsistent ranges rather than inventing evidence", () => {
    const invalid = evidence("a", 0, 5);
    invalid.document.text = "wrong length";
    expect(() => mergeMatchRanges([invalid])).toThrow();
    const inconsistent = evidence("b", 3, 8);
    inconsistent.document.text = "XXXXX";
    expect(() => mergeMatchRanges([evidence("a", 0, 5), inconsistent])).toThrow();
    expect(() => mergeMatchRanges([evidence("a", 0, 4, 1.01)])).toThrow();
  });
  it.each([[0, "low"], [0.4999, "low"], [0.5, "medium"], [0.7999, "medium"], [0.8, "high"], [1, "high"]] as const)(
    "maps %s to %s", (score, level) => expect(scoreLevel(score)).toBe(level),
  );
});
