import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentWorkflow } from "./document-workflow";

function response(status: string, failure_reason: string | null = null) {
  return { ok: true, json: async () => ({ status, failure_reason }) };
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

  it("shows a failed job and provides an explicit retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response("failed", "ocr_required")));
    await act(async () => render(<DocumentWorkflow documentId="doc-id" apiBaseUrl="/api/v1" userId="owner" />));
    expect(screen.getByRole("status")).toHaveTextContent("Analiz başarısız");
    expect(screen.getByRole("alert")).toHaveTextContent("OCR");
    expect(screen.getByRole("button", { name: "Analizi yeniden dene" })).toBeInTheDocument();
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
