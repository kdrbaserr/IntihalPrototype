"use client";

import { useEffect, useRef, useState } from "react";

const STEPS = ["uploaded", "queued", "extracting", "analyzing", "completed"] as const;
type DocumentStatus = (typeof STEPS)[number] | "failed";
const LABELS: Record<DocumentStatus, string> = {
  uploaded: "Yüklendi", queued: "Kuyrukta", extracting: "Metin çıkarılıyor",
  analyzing: "Karşılaştırılıyor", completed: "Analiz tamamlandı", failed: "Analiz başarısız",
};
const DESCRIPTIONS: Record<DocumentStatus, string> = {
  uploaded: "Belgen hazır. Analizi başlatarak metin çıkarma ve karşılaştırma işlemlerini sıraya alabilirsin.",
  queued: "Analiz isteğin alındı. İşlem sırasının veya yeniden deneme bekleme süresinin dolması bekleniyor.",
  extracting: "Belgedeki metin okunuyor ve karşılaştırma için bölümlere ayrılıyor.",
  analyzing: "Metin, izinli kaynaklarla karşılaştırılıyor. Benzer bölümler ve eşleşmeler hazırlanıyor.",
  completed: "Karşılaştırma bitti ve sonuçlar kaydedildi.",
  failed: "Analiz tamamlanamadı. Aşağıdaki açıklamaya göre yeniden deneyebilir veya dosyanı düzeltebilirsin.",
};
const FAILURE_MESSAGES: Record<string, string> = {
  ocr_required: "PDF görüntü içeriyor; OCR uyguladıktan sonra yeniden yükle.",
  processing_timeout: "Analiz için ayrılan süre doldu. Analizi yeniden deneyebilirsin.",
  retry_exhausted: "Servise tekrar denemelerden sonra da ulaşılamadı. Bir süre sonra yeniden deneyebilirsin.",
  processing_failed: "Belge işlenemedi. Yeniden deneyebilirsin; hata sürerse dosyanı kontrol et.",
  invalid_pdf: "PDF açılamadı. Dosyayı yeniden kaydedip tekrar yükle.",
  invalid_docx: "DOCX açılamadı. Dosyayı yeniden kaydedip tekrar yükle.",
  no_extractable_text: "Belgede okunabilir metin bulunamadı. Metin içeren bir dosya yükle.",
  stored_document_changed: "Saklanan dosya yüklenen içerikle eşleşmiyor. Dosyanı yeniden yükle.",
};

export function DocumentWorkflow({ documentId, apiBaseUrl, userId }: {
  documentId: string; apiBaseUrl: string; userId: string;
}) {
  const [status, setStatus] = useState<DocumentStatus>("uploaded");
  const [failure, setFailure] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [lastStage, setLastStage] = useState<(typeof STEPS)[number] | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const submitting = useRef(false);
  const canRetry = analysisId !== null &&
    ["processing_failed", "processing_timeout", "retry_exhausted"].includes(failure ?? "");

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
        if (submitting.current) {
          timer = setTimeout(poll, 2000);
          return;
        }
        setStatus(document.status);
        setLoaded(true);
        if (STEPS.includes(document.status)) setLastStage(document.status);
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
  }, [documentId, apiBaseUrl, userId, refresh]);

  async function start() {
    if (submitting.current) return;
    if (status === "failed" && !canRetry) return;
    submitting.current = true;
    setStarting(true);
    setError("");
    setTraceId(null);
    try {
      const path = status === "failed"
        ? `/analyses/${analysisId}/retry`
        : `/documents/${documentId}/analysis`;
      const response = await fetch(`${apiBaseUrl}${path}`, {
        method: "POST", headers: { "X-User-ID": userId },
      });
      const result = await response.json();
      if (!response.ok) {
        setError(result.detail?.message ?? "Analiz başlatılamadı. Yeniden deneyebilirsin.");
        setTraceId(result.detail?.trace_id ?? null);
        return;
      }
      setAnalysisId(result.id ?? null);
      setStatus(result.status === "completed" ? "completed"
        : result.status === "failed" ? "failed" : "queued");
      if (!["completed", "failed"].includes(result.status)) setLastStage("queued");
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
    <section className="analysis-status" data-status={loaded ? status : "loading"}
      aria-label="Belge analiz durumu">
      <div className="analysis-status-heading">
        <span className="analysis-status-indicator" aria-hidden="true" />
        <p role="status" aria-atomic="true">{loaded ? LABELS[status]
          : error ? "Durum doğrulanamadı" : "Durum kontrol ediliyor…"}</p>
      </div>
      {loaded && <p className="analysis-status-description">{DESCRIPTIONS[status]}</p>}
      <ol className="analysis-stages" aria-label="Analiz aşamaları">
        {STEPS.map((step, index) => {
          const currentIndex = status === "failed" && lastStage !== null
            ? STEPS.indexOf(lastStage) : STEPS.indexOf(status as (typeof STEPS)[number]);
          const state = !loaded ? "pending" : status === "failed"
            ? step === lastStage && step !== "uploaded" ? "interrupted"
              : index < currentIndex || step === "uploaded" ? "done" : "pending"
            : status === "completed" || index < currentIndex ? "done"
              : status === step ? "active" : "pending";
          const stateLabel = { pending: "Bekliyor", done: "Tamamlandı",
            active: "Şu an", interrupted: "İşlem durdu" }[state];
          return <li key={step} data-state={state}
            aria-current={state === "active" ? "step" : undefined}>
            <span className="analysis-stage-marker" aria-hidden="true">{state === "done" ? "✓" : index + 1}</span>
            <div><strong>{LABELS[step]}</strong><span>{stateLabel}</span></div>
          </li>;
        })}
      </ol>
      {loaded && status === "failed" && <div className="analysis-error" role="alert">
        <strong>İşlem tamamlanamadı</strong>
        <p>{FAILURE_MESSAGES[failure ?? ""] ?? "Belge işlenemedi. Dosyanı kontrol edip yeniden yükle."}</p>
        {lastStage && lastStage !== "uploaded" && <p>Son görülen aşama: {LABELS[lastStage]}</p>}
      </div>}
      {error && <div className="analysis-error" role="alert"><p>{error}</p>
        {traceId && <p className="analysis-trace">Destek takip kodu: {traceId}</p>}
      </div>}
      {loaded && (status === "uploaded" || (status === "failed" && canRetry)) && (
        <button type="button" className="upload-button" onClick={start} disabled={starting}>
          {starting ? "Başlatılıyor…" : status === "failed" ? "Analizi yeniden dene" : "Analizi başlat"}
        </button>
      )}
    </section>
  );
}
