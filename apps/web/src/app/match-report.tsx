"use client";

import { useEffect, useState } from "react";

import { MatchEvidence, MergedRange, mergeMatchRanges, SCORE_LABELS, scoreLevel } from "./match-ranges";

function percent(score: number) {
  return new Intl.NumberFormat("tr-TR", { style: "percent", maximumFractionDigits: 1 }).format(score);
}

function sourceUrl(value: string | null) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

export function MatchReport({ analysisId, apiBaseUrl, userId }: {
  analysisId: string; apiBaseUrl: string; userId: string;
}) {
  const [opened, setOpened] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState<{ groups: MergedRange[]; count: number } | null>(null);
  const [error, setError] = useState("");
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
            { headers: { "X-User-ID": userId }, signal: controller.signal },
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
        const groups = mergeMatchRanges(matches);
        if (!controller.signal.aborted) setResult({ groups, count: matches.length });
      } catch {
        if (!controller.signal.aborted) setError("Eşleşmeler okunamadı. Raporu yeniden yükleyebilirsin.");
      }
    }
    void load();
    return () => controller.abort();
  }, [opened, refresh, analysisId, apiBaseUrl, userId]);

  if (!opened) return <button type="button" className="upload-button" onClick={() => setOpened(true)}>
    Eşleşmeleri göster
  </button>;
  return <section className="match-report" aria-label="Eşleşme raporu">
    <h3>Eşleşen bölümler</h3>
    <ul className="match-legend" aria-label="Skor renkleri">
      <li data-level="low">Düşük: %50 altı</li>
      <li data-level="medium">Orta: %50 dahil, %80 hariç</li>
      <li data-level="high">Yüksek: %80 ve üzeri</li>
    </ul>
    <p className="match-note">Çakışan aralıklar birleştirilir; bölüm rengi en yüksek eşleşme skoruna göre seçilir.
      Skor, metin parçalarının benzerliğidir; belgenin genel intihal yüzdesi değildir.</p>
    {error ? <div role="alert" className="analysis-error"><p>{error}</p>
      <button type="button" onClick={() => { setError(""); setResult(null); setRefresh((value) => value + 1); }}>
        Raporu yeniden yükle
      </button>
    </div> : !result ? <p role="status">Eşleşmeler yükleniyor…</p>
      : result.count === 0 ? <p role="status">Bu analizde eşleşme bulunamadı.</p>
        : <>
          <p>{result.count} eşleşme, {result.groups.length} bölümde gösteriliyor.</p>
          {result.groups.map((group) => {
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
                    <blockquote>{match.source.text}</blockquote>
                  </li>;
                })}</ul>
              </details>
            </article>;
          })}
        </>}
  </section>;
}
