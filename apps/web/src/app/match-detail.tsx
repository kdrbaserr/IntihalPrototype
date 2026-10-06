import { MatchEvidence } from "./match-ranges";

export function formatScore(score: number) {
  return new Intl.NumberFormat("tr-TR", { style: "percent", maximumFractionDigits: 1 }).format(score);
}

export function MatchDetail({ match }: { match: MatchEvidence }) {
  const components = match.score_components;
  return <details className="match-detail">
    <summary>Eşleşme ayrıntısı</summary>
    <dl>
      <dt>Belge sayfası</dt><dd>{match.document.page_number ?? "Sayfa bilgisi yok"}</dd>
      <dt>Kaynak dosya</dt><dd>{match.source.original_filename ?? "Belirtilmedi"}</dd>
      <dt>Yazar</dt><dd>{match.source.author ?? "Belirtilmedi"}</dd>
      <dt>Yayıncı</dt><dd>{match.source.publisher ?? "Belirtilmedi"}</dd>
      <dt>Lisans</dt><dd>{match.source.license_name ?? "Belirtilmedi"}</dd>
      <dt>Eşleşen kelime sayısı</dt><dd>{match.matched_token_count ?? "Belirtilmedi"}</dd>
      <dt>Yöntem</dt><dd>{match.method === "hybrid" ? "Hibrit benzerlik" : "Yöntem bilgisi yok"}</dd>
    </dl>
    {match.source.attribution_text && <p>Atıf: {match.source.attribution_text}</p>}
    {match.explanation && <p>{match.explanation}</p>}
    <h4>Belgedeki metin</h4><blockquote>{match.document.text}</blockquote>
    <h4>Kaynaktaki metin</h4><blockquote>{match.source.text}</blockquote>
    {components ? <>
      <p>Skor, iki tam metin parçasının karşılaştırmasına aittir. Algoritma: {components.algorithm_version}</p>
      <div className="match-score-table"><table>
        <caption>Skor bileşenleri</caption>
        <thead><tr><th scope="col">Bileşen</th><th scope="col">Skor</th>
          <th scope="col">Ağırlık</th><th scope="col">Katkı</th></tr></thead>
        <tbody>{([
          ["word_tfidf", "Kelime TF-IDF"], ["character_tfidf", "Karakter TF-IDF"],
          ["word_overlap", "Kelime örtüşmesi"],
        ] as const).map(([key, label]) => <tr key={key}>
          <th scope="row">{label}</th><td>{formatScore(Number(components[key].score))}</td>
          <td>{formatScore(Number(components[key].weight))}</td>
          <td>{formatScore(Number(components[key].contribution))}</td>
        </tr>)}</tbody>
      </table></div>
      <p>Katkı = skor × ağırlık. Katkıların toplamı, yuvarlama farklarıyla toplam benzerlik skorunu verir.</p>
    </> : <p>Bu eşleşmenin skor bileşenleri kaydedilmemiş.</p>}
  </details>;
}
