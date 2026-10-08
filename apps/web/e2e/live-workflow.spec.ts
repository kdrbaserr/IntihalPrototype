import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

const api = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";
const content = "Akademik bir metinde kullanılan düşüncenin kaynağı açıkça belirtilmelidir. " +
  "Doğru atıf, okuyucunun bilginin kökenini izlemesini sağlar.\n\n" +
  "Kaynakça kaydı; yazar, eser adı ve yayın bilgisini tutarlı biçimde sunar. " +
  "Doğrudan alıntılar özgün ifadeyi korur ve uygun konum bilgisiyle gösterilir.";

// Intentionally no page.route(): requests reach the running API, queue and storage.
test("real registration, session, upload, worker analysis, report and deletion", async ({ page, context }, testInfo) => {
  const email = `e2e-${randomUUID()}@example.test`;
  const password = `E2e-${randomUUID()}!`;
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  let documentId: string | undefined;
  let analysisId: string | undefined;
  const headers = { "X-CSRF-Protection": "1" };
  try {
    await page.goto("/");
    await page.getByRole("button", { name: "Yeni hesap oluştur" }).click();
    await page.getByRole("textbox", { name: "Adınız" }).fill("E2E Test Kullanıcısı");
    await page.getByRole("textbox", { name: "E-posta" }).fill(email);
    await page.getByLabel("Parola", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Hesap oluştur", exact: true }).click();
    await expect(page.getByText("Hesabınız oluşturuldu. Giriş yapabilirsiniz.")).toBeVisible();
    await page.getByRole("textbox", { name: "E-posta" }).fill(email);
    await page.getByLabel("Parola", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
    await expect(page.getByRole("button", { name: "Çıkış yap" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("button", { name: "Çıkış yap" })).toBeVisible();
    await page.locator('input[type="file"]').setInputFiles({ name: "live-workflow.txt",
      mimeType: "text/plain", buffer: Buffer.from(content) });
    await page.getByLabel("Belge saklama süresi").selectOption("7");
    const uploaded = page.waitForResponse(response => response.url() === `${api}/documents` && response.request().method() === "POST");
    await page.getByRole("button", { name: "Belgeyi yükle", exact: true }).click();
    const upload = await uploaded;
    expect(upload.status()).toBe(201);
    const document = await upload.json();
    documentId = document.id;
    expect(document.retention_days).toBe(7);
    const started = page.waitForResponse(response => response.url() === `${api}/documents/${documentId}/analysis` && response.request().method() === "POST");
    await page.getByRole("button", { name: "Analizi başlat", exact: true }).click();
    const start = await started;
    expect(start.status()).toBe(202);
    analysisId = (await start.json()).id;
    await expect(page.getByRole("region", { name: "Belge analiz durumu" }).getByRole("status"))
      .toHaveText("Analiz tamamlandı", { timeout: 60_000 });
    await page.getByRole("button", { name: "Eşleşmeleri göster", exact: true }).click();
    await expect(page.locator("mark").first()).toBeVisible();
    const matches = await context.request.get(`${api}/analyses/${analysisId}/matches`);
    expect(matches.status()).toBe(200);
    expect((await matches.json()).total).toBeGreaterThan(0);
    await page.getByRole("button", { name: "Yazdırılabilir görünüm" }).click();
    const preview = page.getByRole("dialog", { name: "Yazdırılabilir analiz raporu" });
    await expect(preview.getByRole("heading", { name: "live-workflow.txt" })).toBeVisible();
    await page.emulateMedia({ media: "print" });
    await expect(page.locator(".site-shell")).toBeHidden();
    await page.pdf({ path: testInfo.outputPath("live-analysis-report.pdf"), preferCSSPageSize: true, printBackground: true });
    await testInfo.attach("live-report", { path: testInfo.outputPath("live-analysis-report.pdf"), contentType: "application/pdf" });
    await page.emulateMedia({ media: "screen" });
    await preview.getByRole("button", { name: "Önizlemeyi kapat" }).click();
    // There is currently no delete button in the UI; verify the real API contract.
    expect((await context.request.delete(`${api}/documents/${documentId}`, { headers })).status()).toBe(204);
    expect((await context.request.get(`${api}/documents/${documentId}`)).status()).toBe(404);
    expect((await context.request.get(`${api}/analyses/${analysisId}`)).status()).toBe(404);
    expect((await context.request.get(`${api}/analyses/${analysisId}/matches`)).status()).toBe(404);
    expect((await context.request.delete(`${api}/documents/${documentId}`, { headers })).status()).toBe(204);
    const list = await context.request.get(`${api}/documents`);
    expect(list.status()).toBe(200);
    expect((await list.json()).some((item: { id: string }) => item.id === documentId)).toBe(false);
    await page.getByRole("button", { name: "Çıkış yap" }).click();
    await expect(page.getByRole("button", { name: "Giriş yap", exact: true })).toBeVisible();
    expect((await context.request.get(`${api}/auth/me`)).status()).toBe(401);
    expect(errors).toEqual([]);
  } finally {
    await testInfo.attach("live-identifiers", { body: JSON.stringify({ email, documentId, analysisId }), contentType: "application/json" });
    // Clean up only this test's document if an earlier assertion failed.
    if (documentId) {
      await context.request.post(`${api}/auth/login`, { headers, data: { email, password } });
      await context.request.delete(`${api}/documents/${documentId}`, { headers });
      await context.request.post(`${api}/auth/logout`, { headers });
    }
  }
});
