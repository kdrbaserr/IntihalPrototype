import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PrintMetadata, PrintReport, reportDate } from "./print-report";
import { MatchEvidence } from "./match-ranges";

const metadata: PrintMetadata = { id: "analysis-1", document_id: "document-1",
  algorithm_version: "classical-hybrid-v1", created_at: "2026-10-07T08:00:00Z",
  started_at: "2026-10-07T08:01:00Z", completed_at: "2026-10-07T08:05:00Z",
  similarity_threshold: "0.8", config_snapshot: {} };
const match: MatchEvidence = { id: "match-1", method: "hybrid", similarity_score: "0.9",
  document: { char_start: 0, char_end: 3, text: "abc", page_number: 1 },
  source: { char_start: 5, char_end: 8, text: "abc", page_number: 2,
    source_document_id: "source-1", title: "Örnek kaynak", source_url: "https://example.com/source",
    author: "Örnek yazar", license_name: "CC0", original_filename: "kaynak.pdf" } };

describe("PrintReport", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });
  it("shows authoritative dates, method, filters, sources, warning and expanded evidence", () => {
    const close = vi.fn();
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<PrintReport metadata={metadata} filename="belgem.pdf" matches={[match]} total={4}
      sourceLabel="Örnek kaynak" minimumScore={80} onClose={close} />);
    const dialog = screen.getByRole("dialog", { name: "Yazdırılabilir analiz raporu" });
    expect(within(dialog).getByText("belgem.pdf")).toBeVisible();
    expect(within(dialog).getByText(/7 Ekim 2026 11:05/)).toBeVisible();
    expect(within(dialog).getByText(/Hibrit benzerlik:/)).toBeVisible();
    expect(within(dialog).getByText("1 / 4 eşleşme, 1 birleşik bölüm.")).toBeVisible();
    expect(within(dialog).getByText(/Benzerlik bulguları tek başına intihal kararı değildir/)).toBeVisible();
    expect(within(dialog).getByRole("link")).toHaveAttribute("href", "https://example.com/source");
    expect(within(dialog).getByText("Belgedeki metin")).toBeVisible();
    expect(dialog.querySelector("details")).toBeNull();
    fireEvent.click(within(dialog).getByRole("button", { name: "Yazdır / PDF olarak kaydet" }));
    expect(print).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(close).toHaveBeenCalledTimes(1);
  });
  it("supports empty filtered results without fabricating sources or dates", () => {
    render(<PrintReport metadata={{ ...metadata, completed_at: null }} filename="belgem.txt"
      matches={[]} total={3} sourceLabel="Tüm kaynaklar" minimumScore={100} onClose={() => {}} />);
    expect(screen.getByText("Seçili kapsamda eşleşme bulunamadı.")).toBeVisible();
    expect(screen.getByText("Seçili kapsamda kaynak bulunamadı.")).toBeVisible();
    expect(screen.getByText(/Tarih bilgisi yok/)).toBeVisible();
    expect(reportDate("invalid-date")).toBe("Tarih bilgisi yok");
  });
  it("lists each source once even when it has several matches", () => {
    render(<PrintReport metadata={metadata} filename="belgem.pdf"
      matches={[match, { ...match, id: "match-2" }]} total={2}
      sourceLabel="Tüm kaynaklar" minimumScore={0} onClose={() => {}} />);
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
