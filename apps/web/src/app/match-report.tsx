"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

import { MatchEvidence, filterMatches, mergeMatchRanges, SCORE_LABELS, scoreLevel } from "./match-ranges";
import { MatchDetail, formatScore as percent } from "./match-detail";
import { PrintMetadata, PrintReport } from "./print-report";

function sourceUrl(value: string | null) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

export function MatchReport({ analysisId, apiBaseUrl }: {
  analysisId: string; apiBaseUrl: string;
}) {
  const [opened, setOpened] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState<MatchEvidence[] | null>(null);
  const [sourceId, setSourceId] = useState("");
  const [minimumScore, setMinimumScore] = useState(0);
  const controlId = useId();
  const [error, setError] = useState("");
  const [printData, setPrintData] = useState<{ metadata: PrintMetadata; filename: string } | null>(null);
  const [printLoading, setPrintLoading] = useState(false);
  const [printError, setPrintError] = useState("");
  const printRequest = useRef(false);
  const printAbort = useRef<AbortController | null>(null);
  useEffect(() => () => printAbort.current?.abort(), []);
  async function preparePrint() {
    if (printRequest.current) return;
    printRequest.current = true;
    const controller = new AbortController();
    printAbort.current = controller;
    setPrintLoading(true);
    setPrintError("");
    try {
      const options = { credentials: "include" as const, signal: controller.signal };
      const response = await fetch(`${apiBaseUrl}/analyses/${analysisId}`, options);
      if (!response.ok) throw new Error("Analysis metadata unavailable");
      const metadata = await response.json();
      if (metadata.id !== analysisId || metadata.status !== "completed" || !metadata.document_id) {
        throw new Error("Invalid analysis metadata");
      }
      const documentResponse = await fetch(`${apiBaseUrl}/documents/${metadata.document_id}`, options);
      if (!documentResponse.ok) throw new Error("Document metadata unavailable");
      const document = await documentResponse.json();
      if (document.id !== metadata.document_id || typeof document.original_filename !== "string") {
        throw new Error("Invalid document metadata");
      }
      if (!controller.signal.aborted) setPrintData({ metadata, filename: document.original_filename });
    } catch {
      if (!controller.signal.aborted) setPrintError("Yazdırma bilgileri alınamadı. Yeniden deneyebilirsin.");
    } finally {
      printRequest.current = false;
      if (!controller.signal.aborted) setPrintLoading(false);
    }
  }
  const filtered = useMemo(() => filterMatches(result ?? [], sourceId, minimumScore / 100),
    [result, sourceId, minimumScore]);
  const groups = useMemo(() => mergeMatchRanges(filtered), [filtered]);
  const sources = useMemo(() => {
    const byId = new Map<string, MatchEvidence["source"]>();
    for (const match of result ?? []) byId.set(match.source.source_document_id, match.source);
    return [...byId.values()].sort((a, b) => a.title.localeCompare(b.title, "tr"));
  }, [result]);
  useEffect(() => {
    if (!opened) return;
    const controller = new AbortController();
    async function load() {
      try {
        const matches: MatchEvidence[] = [];
        let total: number | null = null;
        do {
          const response = await fetch(
            `${apiBaseUrl}/analyses/${analysisId}/matches?limit=100&offset=${matches.length}`,
            { credentials: "include", signal: controller.signal },
          );
          if (!response.ok) throw new Error("Match request failed");
          const page = await response.json();
          if (page.offset_unit !== "unicode_code_points" ||
              page.range_convention !== "start_inclusive_end_exclusive" ||
              !Number.isSafeInteger(page.total) || page.total < 0 || !Array.isArray(page.items) ||
              (total !== null && total !== page.total)) throw new Error("Invalid match page");
          total = page.total;
          if (page.items.length === 0 && matches.length < page.total) throw new Error("Incomplete report");
          matches.push(...page.items);
          if (matches.length > page.total) throw new Error("Invalid total");
        } while (matches.length < total!);
        if (new Set(matches.map((match) => match.id)).size !== matches.length) {
          throw new Error("Duplicate match page");
        }
        mergeMatchRanges(matches); // validate the complete evidence before rendering/filtering
        if (!controller.signal.aborted) setResult(matches);
      } catch {
        if (!controller.signal.aborted) setError("Eşleşmeler okunamadı. Raporu yeniden yükleyebilirsin.");
      }
    }
    void load();
    return () => controller.abort();
  }, [opened, refresh, analysisId, apiBaseUrl]);

  if (!opened) return <button type="button" className="upload-button" onClick={() => setOpened(true)}>
    Eşleşmeleri göster
  </button>;
  return <>
    {printData && result && <PrintReport metadata={printData.metadata} filename={printData.filename}
      matches={filtered} total={result.length} minimumScore={minimumScore}
      sourceLabel={sources.find((source) => source.source_document_id === sourceId)?.title ?? "Tüm kaynaklar"}
      onClose={() => setPrintData(null)} />}
    <section className="match-report" aria-label="Eşleşme raporu">
    <h3>Eşleşen bölümler</h3>
    <ul className="match-legend" aria-label="Skor renkleri">
      <li data-level="low">Düşük: %50 altı</li>
      <li data-level="medium">Orta: %50 dahil, %80 hariç</li>
      <li data-level="high">Yüksek: %80 ve üzeri</li>
    </ul>
    <p className="match-note">Çakışan aralıklar birleştirilir; bölüm rengi en yüksek eşleşme skoruna göre seçilir.
      Skor, metin parçalarının benzerliğidir; belgenin genel intihal yüzdesi değildir.</p>
    {result !== null && !error && <div className="match-print-actions">
      <button type="button" disabled={printLoading} onClick={preparePrint}>
        {printLoading ? "Yazdırma görünümü hazırlanıyor…" : "Yazdırılabilir görünüm"}
      </button>
      {printError && <p role="alert">{printError}</p>}
    </div>}
    {error ? <div role="alert" className="analysis-error"><p>{error}</p>
      <button type="button" onClick={() => { setError(""); setResult(null); setRefresh((value) => value + 1); }}>
        Raporu yeniden yükle
      </button>
    </div> : !result ? <p role="status">Eşleşmeler yükleniyor…</p>
      : result.length === 0 ? <p role="status">Bu analizde eşleşme bulunamadı.</p>
        : <>
          <fieldset className="match-filters"><legend>Eşleşme filtreleri</legend>
            <label htmlFor={`${controlId}-source`}>Kaynak</label>
            <select id={`${controlId}-source`} value={sourceId} onChange={(event) => setSourceId(event.target.value)}>
              <option value="">Tüm kaynaklar</option>
              {sources.map((source) => <option key={source.source_document_id} value={source.source_document_id}>
                {source.title}{sources.filter((other) => other.title === source.title).length > 1
                  ? ` · ${source.original_filename ?? "Kaynak"} · ${source.source_document_id.slice(0, 8)}` : ""}
              </option>)}
            </select>
            <label htmlFor={`${controlId}-score`}>Minimum skor</label>
            <output htmlFor={`${controlId}-score`}>{percent(minimumScore / 100)}</output>
            <input id={`${controlId}-score`} type="range" min="0" max="100" step="1"
              aria-valuetext={percent(minimumScore / 100)}
              value={minimumScore} onChange={(event) => setMinimumScore(Number(event.target.value))} />
            <button type="button" onClick={() => { setSourceId(""); setMinimumScore(0); }}>Filtreleri temizle</button>
          </fieldset>
          <p>{filtered.length} eşleşme, {groups.length} bölümde gösteriliyor.</p>
          <p className="match-note">Toplam {result.length} eşleşmeden filtrelenenler gösteriliyor.
            Analizin kayıtlı skor eşiğinin altındaki eşleşmeler raporda bulunmaz.</p>
          {filtered.length === 0 && <p role="status">Bu filtrelere uygun eşleşme bulunamadı.</p>}
          {groups.map((group) => {
            const level = scoreLevel(group.score);
            return <article className="match-card" key={`${group.start}-${group.end}`} data-level={level}>
              <div className="match-heading"><strong>{SCORE_LABELS[level]} benzerlik · {percent(group.score)}</strong>
                <span>Aralık: [{group.start}, {group.end})</span></div>
              <p className="match-pages">Belge sayfası: {group.pages.map((page) => page ?? "Sayfa bilgisi yok").join(", ")}</p>
              <blockquote><mark data-level={level}>{group.text}</mark></blockquote>
              <details><summary>Kaynakları incele ({group.matches.length} eşleşme)</summary>
                <ul className="match-sources">{group.matches.map((match) => {
                  const url = sourceUrl(match.source.source_url);
                  return <li key={match.id}>
                    <strong>{url ? <a href={url} target="_blank" rel="noopener noreferrer">{match.source.title}</a>
                      : match.source.title}</strong>
                    <p>Skor: {percent(Number(match.similarity_score))} · Kaynak sayfası: {match.source.page_number ?? "Sayfa bilgisi yok"}</p>
                    <p>Belge: [{match.document.char_start}, {match.document.char_end}) · Kaynak: [{match.source.char_start}, {match.source.char_end})</p>
                    <MatchDetail match={match} />
                  </li>;
                })}</ul>
              </details>
            </article>;
          })}
        </>}
  </section></>;
}
