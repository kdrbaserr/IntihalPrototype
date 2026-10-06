import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentWorkflow } from "./document-workflow";

function response(status: string, failure_reason: string | null = null) {
  return { ok: true, json: async () => ({ status, failure_reason,
    id: "analysis-id", latest_analysis_id: "analysis-id" }) };
}

describe("DocumentWorkflow", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

  it("starts analysis and polls through the workflow until completed", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response("uploaded"))
      .mockResolvedValueOnce(response("queued")) // POST accepted
      .mockResolvedValueOnce(response("queued"))
      .mockResolvedValueOnce(response("extracting"))
      .mockResolvedValueOnce(response("analyzing"))
      .mockResolvedValueOnce(response("completed"));
    vi.stubGlobal("fetch", fetcher);
    await act(async () => render(<DocumentWorkflow documentId="doc-id" apiBaseUrl="/api/v1" userId="owner" />));
    expect(screen.getByRole("status")).toHaveTextContent("Yüklendi");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Analizi başlat" })));
    expect(fetcher).toHaveBeenCalledWith("/api/v1/documents/doc-id/analysis", {
      method: "POST", headers: { "X-User-ID": "owner" },
    });
    expect(screen.getByRole("status")).toHaveTextContent("Kuyrukta");
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(screen.getByRole("status")).toHaveTextContent("Metin çıkarılıyor");
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(screen.getByRole("status")).toHaveTextContent("Karşılaştırılıyor");
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(screen.getByRole("status")).toHaveTextContent("Analiz tamamlandı");
    const count = fetcher.mock.calls.length;
    await act(async () => vi.advanceTimersByTimeAsync(10000));
    expect(fetcher.mock.calls.length).toBe(count);
  });

  it("requires a new upload for OCR rather than offering a useless retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response("failed", "ocr_required")));
    await act(async () => render(<DocumentWorkflow documentId="doc-id" apiBaseUrl="/api/v1" userId="owner" />));
    expect(screen.getByRole("status")).toHaveTextContent("Analiz başarısız");
    expect(screen.getByRole("alert")).toHaveTextContent("OCR");
    expect(screen.queryByRole("button", { name: "Analizi yeniden dene" })).not.toBeInTheDocument();
  });

  it("sends only one request when clicked twice before React renders", async () => {
    let complete!: (value: ReturnType<typeof response>) => void;
    const fetcher = vi.fn().mockResolvedValueOnce(response("uploaded"))
      .mockImplementationOnce(() => new Promise((resolve) => { complete = resolve; }))
      .mockResolvedValue(response("queued"));
    vi.stubGlobal("fetch", fetcher);
    await act(async () => render(<DocumentWorkflow documentId="doc-id" apiBaseUrl="/api/v1" userId="owner" />));
    const button = screen.getByRole("button", { name: "Analizi başlat" });
    act(() => { fireEvent.click(button); fireEvent.click(button); });
    expect(fetcher.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(1);
    expect(button).toBeDisabled();
    await act(async () => complete(response("queued")));
    expect(screen.getByRole("status")).toHaveTextContent("Kuyrukta");
  });

  it("uses the failed analysis ID for retry and shows the server limit message", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response("failed", "retry_exhausted"))
      .mockResolvedValueOnce({ ok: false, json: async () => ({ detail: {
        code: "analysis_retry_limit", message: "Bu belge için yeniden deneme sınırına ulaşıldı.",
      } }) });
    vi.stubGlobal("fetch", fetcher);
    await act(async () => render(<DocumentWorkflow documentId="doc-id" apiBaseUrl="/api/v1" userId="owner" />));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Analizi yeniden dene" })));
    expect(fetcher).toHaveBeenLastCalledWith("/api/v1/analyses/analysis-id/retry", {
      method: "POST", headers: { "X-User-ID": "owner" },
    });
    expect(screen.getAllByRole("alert").some((item) => item.textContent?.includes("sınırına"))).toBe(true);
    expect(screen.getByRole("status")).toHaveTextContent("Analiz başarısız");
  });

  it("does not mark an existing failed analysis as queued after a repeated start", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response("uploaded"))
      .mockResolvedValue(response("failed", "processing_failed"));
    vi.stubGlobal("fetch", fetcher);
    await act(async () => render(<DocumentWorkflow documentId="doc-id" apiBaseUrl="/api/v1" userId="owner" />));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Analizi başlat" })));
    expect(screen.getByRole("status")).toHaveTextContent("Analiz başarısız");
  });

  it("does not present a connection failure as document failure", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValue(response("analyzing"));
    vi.stubGlobal("fetch", fetcher);
    await act(async () => render(<DocumentWorkflow documentId="doc-id" apiBaseUrl="/api/v1" userId="owner" />));
    expect(screen.getByRole("alert")).toHaveTextContent("durumu okunamadı");
    await act(async () => vi.advanceTimersByTimeAsync(5000));
    expect(screen.getByRole("status")).toHaveTextContent("Karşılaştırılıyor");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
