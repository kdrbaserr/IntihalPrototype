import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MatchReport } from "./match-report";
import { MatchEvidence } from "./match-ranges";

function match(id: string, start: number, end: number, score: string): MatchEvidence {
  const text = "abcdefghij".slice(start, end);
  return { id, similarity_score: score,
    document: { char_start: start, char_end: end, text, page_number: 2 },
    source: { char_start: 0, char_end: end - start, text, page_number: 5,
      title: `Kaynak ${id}`, source_document_id: id, source_url: null } };
}
function page(items: MatchEvidence[], total = items.length) {
  return { ok: true, json: async () => ({ total, items, offset_unit: "unicode_code_points",
    range_convention: "start_inclusive_end_exclusive" }) };
}
function open() {
  render(<MatchReport analysisId="analysis-id" apiBaseUrl="/api/v1" userId="owner" />);
  fireEvent.click(screen.getByRole("button", { name: "Eşleşmeleri göster" }));
}

describe("MatchReport", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
  it("loads all pages before merging cross-page overlap and preserves both sources", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(page([match("a", 0, 5, "0.6")], 2))
      .mockResolvedValueOnce(page([match("b", 3, 10, "0.9")], 2));
    vi.stubGlobal("fetch", fetcher);
    open();
    await screen.findByText("2 eşleşme, 1 bölümde gösteriliyor.");
    expect(fetcher.mock.calls[0][0]).toBe("/api/v1/analyses/analysis-id/matches?limit=100&offset=0");
    expect(fetcher.mock.calls[1][0]).toBe("/api/v1/analyses/analysis-id/matches?limit=100&offset=1");
    expect(fetcher.mock.calls[0][1].headers).toEqual({ "X-User-ID": "owner" });
    const mark = screen.getByText("abcdefghij");
    expect(mark.tagName).toBe("MARK");
    expect(mark).toHaveAttribute("data-level", "high");
    expect(screen.getByText("Kaynak a")).toBeInTheDocument();
    expect(screen.getByText("Kaynak b")).toBeInTheDocument();
    expect(screen.getByText("Belge sayfası: 2")).toBeInTheDocument();
    expect(screen.getAllByText(/Kaynak sayfası: 5/)).toHaveLength(2);
  });
  it("handles empty results", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(page([])));
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("eşleşme bulunamadı");
  });
  it("allows recovery from fetch failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue(page([])));
    open();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Raporu yeniden yükle" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("eşleşme bulunamadı"));
  });
  it("does not render a partial report when a later page fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(page([match("a", 0, 5, "0.5")], 2))
      .mockRejectedValueOnce(new Error("offline")));
    open();
    await screen.findByRole("alert");
    expect(screen.queryByText("Kaynak a")).not.toBeInTheDocument();
  });
  it("renders source text safely and rejects executable links", async () => {
    const item = match("a", 0, 5, "0.3");
    item.source.title = "<script>unsafe</script>";
    item.source.source_url = "javascript:alert(1)";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(page([item])));
    open();
    await screen.findByText("<script>unsafe</script>");
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("abcde", { selector: "mark" })).toHaveAttribute("data-level", "low");
  });
});
