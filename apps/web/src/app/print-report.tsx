"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { MatchDetail, formatScore } from "./match-detail";
import { MatchEvidence, mergeMatchRanges, SCORE_LABELS, scoreLevel } from "./match-ranges";

export type PrintMetadata = {
  id: string; document_id: string; algorithm_version: string;
  completed_at: string | null; started_at: string | null; created_at: string;
  similarity_threshold: string | number;
  config_snapshot: Record<string, string>;
};

export function reportDate(value: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return "Tarih bilgisi yok";
  return new Intl.DateTimeFormat("tr-TR", { dateStyle: "long", timeStyle: "short",
    timeZone: "Europe/Istanbul" }).format(new Date(value));
}

function safeUrl(value: string | null) {
  try {
    const url = new URL(value ?? "");
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

export function PrintReport({ metadata, filename, matches, total, sourceLabel, minimumScore, onClose }: {
  metadata: PrintMetadata; filename: string; matches: MatchEvidence[]; total: number;
  sourceLabel: string; minimumScore: number; onClose: () => void;
}) {
  const dialog = useRef<HTMLDivElement>(null);
  const printButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    printButton.current?.focus();
    return () => previous?.focus();
  }, []);
  const groups = mergeMatchRanges(matches);
  const sources = [...new Map(matches.map((match) =>
    [match.source.source_document_id, match.source])).values()];
  return createPortal(<div className="print-preview" role="dialog" aria-modal="true"
    aria-label="Yazdırılabilir analiz raporu" ref={dialog}
    onKeyDown={(event) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key === "Tab") {
        const controls = dialog.current?.querySelectorAll<HTMLElement>("button, a[href]");
        const first = controls?.[0], last = controls?.[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }}>
    <div className="print-toolbar">
      <button type="button" ref={printButton} onClick={() => window.print()}>Yazdır / PDF olarak kaydet</button>
      <button type="button" onClick={onClose}>Önizlemeyi kapat</button>
    </div>
    <article className="print-document">
      <header><p>İntihal Prototype · Benzerlik raporu</p><h1>{filename}</h1>
        <p>Analiz kimliği: {metadata.id}</p></header>
      <dl className="print-metadata">
        <dt>Yöntem</dt><dd>Hibrit benzerlik: kelime TF-IDF, karakter TF-IDF ve kelime örtüşmesi.</dd>
        <dt>Algoritma sürümü</dt><dd>{metadata.algorithm_version}</dd>
        <dt>Analiz tarihi</dt><dd>{reportDate(metadata.completed_at)} (Türkiye saati)</dd>
        <dt>Analiz başlangıcı</dt><dd>{reportDate(metadata.started_at)}</dd>
        <dt>Analiz eşiği</dt><dd>{formatScore(Number(metadata.similarity_threshold))}</dd>
        <dt>Kaynak filtresi</dt><dd>{sourceLabel}</dd>
        <dt>Minimum görünüm skoru</dt><dd>{formatScore(minimumScore / 100)}</dd>
        <dt>Rapor kapsamı</dt><dd>{matches.length} / {total} eşleşme, {groups.length} birleşik bölüm.</dd>
      </dl>
      <aside className="print-warning"><h2>Uyarı</h2><p>Benzerlik bulguları tek başına intihal kararı değildir.
        Sistem yalnız izinli kaynak havuzuyla karşılaştırma yapar; eşleşme bulunmaması özgünlüğü kanıtlamaz.
        Akademik değerlendirme kullanıcıya ve yetkili inceleyiciye aittir.</p>
        <p>Bu çıktı seçili kaynak ve minimum skor filtrelerini içerir. Skorlar metin parçalarının
          benzerliğidir; belgenin genel intihal yüzdesi değildir. Birleşik bölümün seviyesi en yüksek
          eşleşme skoruna göre belirlenir. Aralıklar normalize edilmiş metinde başlangıç dahil,
          bitiş hariç Unicode karakter konumlarıdır.</p></aside>
      <section><h2>Eşleşen bölümler</h2>
        <p>Düşük: %50 altı · Orta: %50 dahil, %80 hariç · Yüksek: %80 ve üzeri.</p>
        {matches.length === 0 && <p>Seçili kapsamda eşleşme bulunamadı.</p>}
        {groups.map((group, index) => <section className="print-match" key={`${group.start}-${group.end}`}>
          <h3>Bölüm {index + 1}: {SCORE_LABELS[scoreLevel(group.score)]} · {formatScore(group.score)}</h3>
          <p>Belge aralığı: [{group.start}, {group.end}) · Sayfa: {group.pages.map((page) => page ?? "Sayfa bilgisi yok").join(", ")}</p>
          <blockquote><mark data-level={scoreLevel(group.score)}>{group.text}</mark></blockquote>
          {group.matches.map((match) => <section className="print-evidence" key={match.id}>
            <h4>Kaynak: {match.source.title} · Skor: {formatScore(Number(match.similarity_score))}</h4>
            <p>Belge: [{match.document.char_start}, {match.document.char_end}) · Kaynak: [{match.source.char_start}, {match.source.char_end})
              · Kaynak sayfası: {match.source.page_number ?? "Sayfa bilgisi yok"}</p>
            <MatchDetail match={match} printable />
          </section>)}
        </section>)}
      </section>
      <section className="print-source-list"><h2>Kaynaklar</h2>
        {sources.length === 0 && <p>Seçili kapsamda kaynak bulunamadı.</p>}
        <ol>{sources.map((source) => <li key={source.source_document_id}>
          <strong>{source.title}</strong><p>{source.author ?? "Yazar belirtilmedi"} · {source.publisher ?? "Yayıncı belirtilmedi"}
            · {source.original_filename ?? "Dosya adı belirtilmedi"}</p>
          <p>Lisans: {source.license_name ?? "Belirtilmedi"}{source.attribution_text && ` · ${source.attribution_text}`}</p>
          {safeUrl(source.source_url) && <p>URL: <a href={safeUrl(source.source_url)!}>{source.source_url}</a></p>}
        </li>)}</ol>
      </section>
    </article>
  </div>, document.body);
}
