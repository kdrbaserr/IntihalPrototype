import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
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
    expect(screen.getByText("Kaynak a", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("Kaynak b", { selector: "strong" })).toBeInTheDocument();
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
    await screen.findByText("<script>unsafe</script>", { selector: "strong" });
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("abcde", { selector: "mark" })).toHaveAttribute("data-level", "low");
  });

  it("combines source and minimum-score filters before merging and resets without refetching", async () => {
    const fetcher = vi.fn().mockResolvedValue(page([
      match("a", 0, 3, "0.8"), match("bridge", 2, 8, "0.4"), match("b", 7, 10, "0.9"),
    ]));
    vi.stubGlobal("fetch", fetcher);
    open();
    await screen.findByText("3 eşleşme, 1 bölümde gösteriliyor.");
    fireEvent.change(screen.getByRole("slider", { name: "Minimum skor" }), { target: { value: "80" } });
    expect(screen.getByText("2 eşleşme, 2 bölümde gösteriliyor.")).toBeInTheDocument();
    expect(screen.getByText("abc", { selector: "mark" })).toBeInTheDocument();
    expect(screen.getByText("hij", { selector: "mark" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Kaynak" }), { target: { value: "a" } });
    expect(screen.getByText("1 eşleşme, 1 bölümde gösteriliyor.")).toBeInTheDocument();
    expect(screen.queryByText("Kaynak b", { selector: "strong" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("slider", { name: "Minimum skor" }), { target: { value: "81" } });
    expect(screen.getByText("Bu filtrelere uygun eşleşme bulunamadı.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Filtreleri temizle" }));
    expect(screen.getByText("3 eşleşme, 1 bölümde gösteriliyor.")).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("updates highlight color when the high-score source is excluded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(page([
      match("low", 0, 5, "0.3"), match("high", 3, 10, "0.9"),
    ])));
    open();
    await screen.findByText("2 eşleşme, 1 bölümde gösteriliyor.");
    fireEvent.change(screen.getByRole("combobox", { name: "Kaynak" }), { target: { value: "low" } });
    expect(screen.getByText("abcde", { selector: "mark" })).toHaveAttribute("data-level", "low");
    expect(screen.queryByText("abcdefghij")).not.toBeInTheDocument();
  });

  it("shows individual evidence, metadata and persisted score components in details", async () => {
    const item = match("a", 0, 5, "0.8");
    item.method = "hybrid";
    item.matched_token_count = 3;
    item.source.original_filename = "kaynak.pdf";
    item.source.author = "Örnek Yazar";
    item.source.license_name = "CC0";
    const signal = { score: "0.8", weight: "0.5", contribution: "0.4" };
    item.score_components = { scope: "chunk_pair", algorithm_version: "classical-hybrid-v1",
      word_tfidf: signal,
      character_tfidf: { score: "1", weight: "0.3", contribution: "0.3" },
      word_overlap: { score: "0.5", weight: "0.2", contribution: "0.1" } };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(page([item])));
    open();
    await screen.findByText("1 eşleşme, 1 bölümde gösteriliyor.");
    fireEvent.click(screen.getByText("Kaynakları incele (1 eşleşme)"));
    fireEvent.click(screen.getByText("Eşleşme ayrıntısı"));
    expect(screen.getByText("kaynak.pdf")).toBeVisible();
    expect(screen.getByText("Örnek Yazar")).toBeVisible();
    expect(screen.getByText("Hibrit benzerlik")).toBeVisible();
    const table = screen.getByRole("table", { name: "Skor bileşenleri" });
    expect(within(table).getByRole("row", { name: "Kelime TF-IDF %80 %50 %40" })).toBeVisible();
    expect(screen.getByText("Belgedeki metin")).toBeVisible();
    expect(screen.getByText("Kaynaktaki metin")).toBeVisible();
  });

  it("distinguishes sources with the same title by ID and supports legacy details", async () => {
    const a = match("a", 0, 3, "0.8");
    const b = match("b", 7, 10, "0.9");
    a.source.title = b.source.title = "Ortak başlık";
    a.source.original_filename = b.source.original_filename = "kaynak.txt";
    a.score_components = null;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(page([a, b])));
    open();
    await screen.findByText("2 eşleşme, 2 bölümde gösteriliyor.");
    expect(screen.getByRole("option", { name: "Ortak başlık · kaynak.txt · a" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Ortak başlık · kaynak.txt · b" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Kaynak" }), { target: { value: "a" } });
    expect(screen.getByText("1 eşleşme, 1 bölümde gösteriliyor.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Kaynakları incele (1 eşleşme)"));
    fireEvent.click(screen.getByText("Eşleşme ayrıntısı"));
    expect(screen.getByText("Bu eşleşmenin skor bileşenleri kaydedilmemiş.")).toBeVisible();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("fetches analysis and document metadata before opening filtered print preview", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(page([match("a", 0, 3, "0.8"), match("b", 7, 10, "0.9")]))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: "analysis-id", status: "completed",
        document_id: "doc-id", algorithm_version: "classical-hybrid-v1",
        completed_at: "2026-10-07T10:00:00Z", started_at: null, similarity_threshold: "0.8" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ id: "doc-id", original_filename: "belgem.pdf" }) });
    vi.stubGlobal("fetch", fetcher);
    open();
    await screen.findByText("2 eşleşme, 2 bölümde gösteriliyor.");
    fireEvent.change(screen.getByRole("combobox", { name: "Kaynak" }), { target: { value: "a" } });
    fireEvent.click(screen.getByRole("button", { name: "Yazdırılabilir görünüm" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("1 / 2 eşleşme, 1 birleşik bölüm.")).toBeVisible();
    expect(within(dialog).queryByText("Kaynak b", { selector: "strong" })).not.toBeInTheDocument();
    expect(fetcher.mock.calls[1][0]).toBe("/api/v1/analyses/analysis-id");
    expect(fetcher.mock.calls[2][0]).toBe("/api/v1/documents/doc-id");
    expect(fetcher.mock.calls[1][1].headers).toEqual({ "X-User-ID": "owner" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Önizlemeyi kapat" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("does not open a printable report if authoritative metadata cannot be loaded", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(page([]))
      .mockResolvedValue({ ok: false }));
    open();
    await screen.findByText("Bu analizde eşleşme bulunamadı.");
    fireEvent.click(screen.getByRole("button", { name: "Yazdırılabilir görünüm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Yazdırma bilgileri alınamadı");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
