"use client";

import { useEffect, useRef, useState } from "react";

const STEPS = ["uploaded", "queued", "extracting", "analyzing", "completed"] as const;
type DocumentStatus = (typeof STEPS)[number] | "failed";
const LABELS: Record<DocumentStatus, string> = {
  uploaded: "Yüklendi", queued: "Kuyrukta", extracting: "Metin çıkarılıyor",
  analyzing: "Karşılaştırılıyor", completed: "Analiz tamamlandı", failed: "Analiz başarısız",
};

export function DocumentWorkflow({ documentId, apiBaseUrl, onSessionExpired }: {
  documentId: string; apiBaseUrl: string; onSessionExpired?: () => void;
}) {
  const [status, setStatus] = useState<DocumentStatus>("uploaded");
  const [failure, setFailure] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const submitting = useRef(false);
  const canRetry = analysisId !== null &&
    ["processing_failed", "processing_timeout", "retry_exhausted"].includes(failure ?? "");

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const response = await fetch(`${apiBaseUrl}/documents/${documentId}`, {
          credentials: "include", signal: controller.signal,
        });
        if (response.status === 401) {
          onSessionExpired?.();
          setError("Oturumunuz sona erdi. Yeniden giriş yapın.");
          return;
        }
        if (!response.ok) throw new Error("status request failed");
        const document = await response.json();
        if (![...STEPS, "failed"].includes(document.status)) throw new Error("unknown status");
        if (controller.signal.aborted) return;
        if (submitting.current) {
          timer = setTimeout(poll, 2000);
          return;
        }
        setStatus(document.status);
        setFailure(document.failure_reason ?? null);
        setAnalysisId(document.latest_analysis_id ?? null);
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
  }, [documentId, apiBaseUrl, refresh, onSessionExpired]);

  async function start() {
    if (submitting.current) return;
    if (status === "failed" && !canRetry) return;
    submitting.current = true;
    setStarting(true);
    setError("");
    try {
      const path = status === "failed"
        ? `/analyses/${analysisId}/retry`
        : `/documents/${documentId}/analysis`;
      const response = await fetch(`${apiBaseUrl}${path}`, {
        method: "POST", credentials: "include", headers: { "X-CSRF-Protection": "1" },
      });
      if (response.status === 401) {
        onSessionExpired?.();
        setError("Oturumunuz sona erdi. Yeniden giriş yapın.");
        return;
      }
      const result = await response.json();
      if (!response.ok) {
        setError(result.detail?.message ?? "Analiz başlatılamadı. Yeniden deneyebilirsin.");
        return;
      }
      setAnalysisId(result.id ?? null);
      setStatus(result.status === "completed" ? "completed"
        : result.status === "failed" ? "failed" : "queued");
      setFailure(result.failure_reason ?? null);
      setRefresh((value) => value + 1);
    } catch {
      setError("Analiz başlatılamadı. Yeniden deneyebilirsin.");
    } finally {
      submitting.current = false;
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
      {(status === "uploaded" || (status === "failed" && canRetry)) && (
        <button type="button" className="upload-button" onClick={start} disabled={starting}>
          {starting ? "Başlatılıyor…" : status === "failed" ? "Analizi yeniden dene" : "Analizi başlat"}
        </button>
      )}
      {status === "completed" && <p>Karşılaştırma bitti ve sonuçlar kaydedildi.</p>}
    </section>
  );
}
