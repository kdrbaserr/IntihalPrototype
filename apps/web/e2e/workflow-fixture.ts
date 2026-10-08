import { expect, Page } from "@playwright/test";

const documentId = "11111111-2222-3333-4444-555555555555";
const initialAnalysisId = "22222222-2222-3333-4444-555555555555";
const retryAnalysisId = "33333333-2222-3333-4444-555555555555";
const text = "abcdefghij";

export async function workflowApi(page: Page, options: { timeout?: boolean; reportFailure?: boolean; uploadFailure?: boolean } = {}) {
  let analysisId = initialAnalysisId;
  let started = false;
  let retried = false;
  let statusIndex = 0;
  let reportFailed = false;
  const counts = { uploads: 0, starts: 0, retries: 0, reports: 0, polls: 0 };
  const statuses = () => options.timeout && !retried
    ? ["queued", "extracting", "failed"] : ["queued", "extracting", "analyzing", "completed"];
  const document = (status: string) => ({ id: documentId, original_filename: "ornek.txt",
    content_type: "text/plain", size_bytes: 10, sha256: "a".repeat(64), status,
    failure_reason: status === "failed" ? "processing_timeout" : null,
    latest_analysis_id: started ? analysisId : null });
  const match = (id: string, start: number, end: number, score: string) => ({
    id, analysis_id: analysisId, similarity_score: score, method: "hybrid", matched_token_count: 2,
    document: { chunk_id: "chunk", char_start: start, char_end: end, text: text.slice(start, end), page_number: null },
    source: { chunk_id: id, source_document_id: id, char_start: 0, char_end: end - start,
      text: text.slice(start, end), page_number: 1, title: `Kaynak ${id}`, source_url: "https://example.com/source",
      original_filename: "kaynak.pdf", author: "Örnek Yazar", license_name: "CC0" },
    score_components: { scope: "chunk_pair", algorithm_version: "classical-hybrid-v1",
      word_tfidf: { score: "1", weight: "0.5", contribution: "0.5" },
      character_tfidf: { score: "1", weight: "0.3", contribution: "0.3" },
      word_overlap: { score: "1", weight: "0.2", contribution: "0.2" } },
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });
    expect(request.headers()["x-user-id"]).toBeUndefined();
    if (path === "/api/v1/auth/me") return json({
      id: "11111111-1111-1111-1111-111111111111", email: "fixture@example.test",
      display_name: "Test Kullanıcı", role: "user",
    });
    if (path === "/api/v1/documents" && request.method() === "POST") {
      counts.uploads++;
      expect(request.headers()["content-type"]).toContain("multipart/form-data");
      expect(request.postData()).toContain('filename="ornek.txt"');
      expect(request.postData()).toContain(text);
      if (options.uploadFailure) return json({ detail: { code: "storage_unavailable",
        message: "Dosya depolama servisine şu anda ulaşılamıyor." } }, 503);
      return json(document("uploaded"), 201);
    }
    if (path === `/api/v1/documents/${documentId}/analysis` && request.method() === "POST") {
      counts.starts++; started = true;
      return json({ id: analysisId, status: "queued", failure_reason: null }, 202);
    }
    if (path === `/api/v1/analyses/${initialAnalysisId}/retry` && request.method() === "POST") {
      counts.retries++; retried = true; statusIndex = 0; analysisId = retryAnalysisId;
      return json({ id: analysisId, status: "queued", failure_reason: null }, 202);
    }
    if (path === `/api/v1/documents/${documentId}`) {
      counts.polls++;
      const state = started ? statuses()[Math.min(statusIndex++, statuses().length - 1)] : "uploaded";
      return json(document(state));
    }
    if (path === `/api/v1/analyses/${analysisId}/matches`) {
      counts.reports++;
      if (options.reportFailure && !reportFailed) {
        reportFailed = true;
        return json({ detail: { code: "storage_unavailable" } }, 503);
      }
      const all = [match("a", 0, 5, "1.0000"), match("b", 3, 10, "1.0000")];
      const offset = Number(url.searchParams.get("offset"));
      return json({ analysis_id: analysisId, total: 2, limit: 100, offset,
        offset_unit: "unicode_code_points", range_convention: "start_inclusive_end_exclusive",
        items: all.slice(offset, offset + 1) });
    }
    if (path === `/api/v1/analyses/${analysisId}`) return json({ id: analysisId, document_id: documentId,
      status: "completed", algorithm_version: "classical-hybrid-v1", similarity_threshold: "0.8",
      started_at: "2026-10-07T08:01:00Z", completed_at: "2026-10-07T08:05:00Z",
      created_at: "2026-10-07T08:00:00Z", config_snapshot: {} });
    return json({ detail: { code: "not_found" } }, 404);
  });
  return counts;
}

export async function uploadAndStart(page: Page) {
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "ornek.txt", mimeType: "text/plain", buffer: Buffer.from(text) });
  await page.getByRole("button", { name: "Belgeyi yükle", exact: true }).click();
  await expect(page.getByRole("button", { name: "Analizi başlat", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Analizi başlat", exact: true }).click();
}
