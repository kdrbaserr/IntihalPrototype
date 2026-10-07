import { expect, test } from "@playwright/test";
import { uploadAndStart, workflowApi } from "./workflow-fixture";

test("upload, wait for each stage, filter evidence and open printable report", async ({ page }, testInfo) => {
  const counts = await workflowApi(page);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await uploadAndStart(page);
  const status = page.getByRole("region", { name: "Belge analiz durumu" }).getByRole("status");
  await expect(status).toHaveText("Kuyrukta");
  await expect(status).toHaveText("Metin çıkarılıyor");
  await expect(status).toHaveText("Karşılaştırılıyor");
  await expect(status).toHaveText("Analiz tamamlandı");
  await page.getByRole("button", { name: "Eşleşmeleri göster", exact: true }).click();
  await expect(page.getByText("2 eşleşme, 1 bölümde gösteriliyor.")).toBeVisible();
  await expect(page.locator("mark")).toHaveText("abcdefghij");
  await expect(page.locator("mark")).toHaveAttribute("data-level", "high");
  await page.getByRole("slider", { name: "Minimum skor" }).focus();
  await page.getByRole("slider", { name: "Minimum skor" }).press("End");
  await page.getByRole("combobox", { name: "Kaynak" }).selectOption("a");
  await expect(page.getByText("1 eşleşme, 1 bölümde gösteriliyor.")).toBeVisible();
  await expect(page.locator("mark")).toHaveText("abcde");
  await page.getByText("Kaynakları incele (1 eşleşme)").click();
  await page.getByText("Eşleşme ayrıntısı", { exact: true }).click();
  await expect(page.getByRole("table", { name: "Skor bileşenleri" })).toBeVisible();
  await page.getByRole("button", { name: "Yazdırılabilir görünüm" }).click();
  const preview = page.getByRole("dialog", { name: "Yazdırılabilir analiz raporu" });
  await expect(preview).toBeVisible();
  await expect(preview.getByRole("heading", { name: "ornek.txt" })).toBeVisible();
  await expect(preview.getByText(/7 Ekim 2026 11:05/)).toBeVisible();
  await expect(preview.getByText(/Benzerlik bulguları tek başına intihal kararı değildir/)).toBeVisible();
  await expect(preview.getByText("1 / 2 eşleşme, 1 birleşik bölüm.")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByRole("button", { name: "Yazdır / PDF olarak kaydet" })).toBeHidden();
  await expect(page.locator(".site-shell")).toBeHidden();
  await page.screenshot({ path: testInfo.outputPath("print-preview.png"), fullPage: true });
  await page.pdf({ path: testInfo.outputPath("analysis-report.pdf"), preferCSSPageSize: true, printBackground: true });
  await testInfo.attach("print-preview", { path: testInfo.outputPath("print-preview.png"), contentType: "image/png" });
  await testInfo.attach("analysis-report", { path: testInfo.outputPath("analysis-report.pdf"), contentType: "application/pdf" });
  await page.emulateMedia({ media: "screen" });
  await preview.getByRole("button", { name: "Önizlemeyi kapat" }).click();
  expect(counts.uploads).toBe(1);
  expect(counts.starts).toBe(1);
  expect(counts.reports).toBe(2);
  expect(errors).toEqual([]);
});

test("timeout is visible and manual retry progresses to a completed report", async ({ page }) => {
  const counts = await workflowApi(page, { timeout: true });
  await uploadAndStart(page);
  const status = page.getByRole("region", { name: "Belge analiz durumu" }).getByRole("status");
  await expect(status).toHaveText("Analiz başarısız");
  await expect(page.getByRole("region", { name: "Belge analiz durumu" }).getByRole("alert"))
    .toContainText("ayrılan süre doldu");
  await page.getByRole("button", { name: "Analizi yeniden dene" }).click();
  await expect(status).toHaveText("Kuyrukta");
  await expect(status).toHaveText("Analiz tamamlandı");
  await page.getByRole("button", { name: "Eşleşmeleri göster", exact: true }).click();
  await expect(page.getByText("2 eşleşme, 1 bölümde gösteriliyor.")).toBeVisible();
  expect(counts.retries).toBe(1);
  expect(counts.starts).toBe(1);
});

test("report fetch failure can be retried without starting another analysis", async ({ page }) => {
  const counts = await workflowApi(page, { reportFailure: true });
  await uploadAndStart(page);
  await expect(page.getByRole("region", { name: "Belge analiz durumu" }).getByRole("status"))
    .toHaveText("Analiz tamamlandı");
  await page.getByRole("button", { name: "Eşleşmeleri göster", exact: true }).click();
  await expect(page.getByRole("region", { name: "Eşleşme raporu" }).getByRole("alert"))
    .toContainText("Eşleşmeler okunamadı");
  await page.getByRole("button", { name: "Raporu yeniden yükle" }).click();
  await expect(page.getByText("2 eşleşme, 1 bölümde gösteriliyor.")).toBeVisible();
  expect(counts.starts).toBe(1);
  expect(counts.reports).toBe(3);
});

test("failed upload does not enable analysis or show a success state", async ({ page }) => {
  const counts = await workflowApi(page, { uploadFailure: true });
  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({ name: "ornek.txt", mimeType: "text/plain", buffer: Buffer.from("abcdefghij") });
  await page.getByRole("button", { name: "Belgeyi yükle", exact: true }).click();
  await expect(page.locator(".upload-panel").getByRole("alert")).toContainText("Dosya depolama servisine");
  await expect(page.getByRole("button", { name: "Analizi başlat", exact: true })).toHaveCount(0);
  expect(counts.uploads).toBe(1);
  expect(counts.starts).toBe(0);
});
