"use client";

import { useEffect, useState } from "react";

const STEPS = ["uploaded", "queued", "extracting", "analyzing", "completed"] as const;
type DocumentStatus = (typeof STEPS)[number] | "failed";
const LABELS: Record<DocumentStatus, string> = {
  uploaded: "Yüklendi", queued: "Kuyrukta", extracting: "Metin çıkarılıyor",
  analyzing: "Karşılaştırılıyor", completed: "Analiz tamamlandı", failed: "Analiz başarısız",
};

export function DocumentWorkflow({ documentId, apiBaseUrl, userId }: {
  documentId: string; apiBaseUrl: string; userId: string;
}) {
  const [status, setStatus] = useState<DocumentStatus>("uploaded");
  const [failure, setFailure] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const response = await fetch(`${apiBaseUrl}/documents/${documentId}`, {
          headers: { "X-User-ID": userId }, signal: controller.signal,
        });
        if (!response.ok) throw new Error("status request failed");
        const document = await response.json();
        if (![...STEPS, "failed"].includes(document.status)) throw new Error("unknown status");
        if (controller.signal.aborted) return;
        setStatus(document.status);
        setFailure(document.failure_reason ?? null);
        setError("");
        if (!["completed", "failed"].includes(document.status)) timer = setTimeout(poll, 2000);
      } catch {
        if (!controller.signal.aborted) {
          setError("Analiz durumu okunamadı. Bağlantı geldiğinde tekrar kontrol edilecek.");
          timer = setTimeout(poll, 5000);
        }
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [documentId, apiBaseUrl, userId, refresh]);

  async function start() {
    setStarting(true);
    setError("");
    try {
      const response = await fetch(`${apiBaseUrl}/documents/${documentId}/analysis`, {
        method: "POST", headers: { "X-User-ID": userId },
      });
      if (!response.ok) throw new Error("analysis request failed");
      setStatus("queued");
      setFailure(null);
      setRefresh((value) => value + 1);
    } catch {
      setError("Analiz başlatılamadı. Yeniden deneyebilirsin.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <section aria-label="Belge analiz durumu">
      <p role="status">{LABELS[status]}</p>
      <ol aria-label="Analiz aşamaları">
        {STEPS.map((step) => (
          <li key={step} aria-current={status === step ? "step" : undefined}>
            {LABELS[step]}
          </li>
        ))}
      </ol>
      {failure && <p role="alert">{failure === "ocr_required"
        ? "PDF görüntü içeriyor; OCR uyguladıktan sonra yeniden yükle."
        : "Belge işlenemedi. Dosyanı kontrol edip yeniden deneyebilirsin."}</p>}
      {error && <p role="alert">{error}</p>}
      {["uploaded", "failed"].includes(status) && (
        <button type="button" className="upload-button" onClick={start} disabled={starting}>
          {starting ? "Başlatılıyor…" : status === "failed" ? "Analizi yeniden dene" : "Analizi başlat"}
        </button>
      )}
      {status === "completed" && <p>Karşılaştırma bitti ve sonuçlar kaydedildi.</p>}
    </section>
  );
}
