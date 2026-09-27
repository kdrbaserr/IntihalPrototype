"use client";

import { ChangeEvent, useRef, useState } from "react";

const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024;
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const DEMO_USER_ID =
  process.env.NEXT_PUBLIC_DEMO_USER_ID ?? "11111111-1111-1111-1111-111111111111";

const ALLOWED_TYPES = new Map([
  ["pdf", "application/pdf"],
  ["docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
  ["txt", "text/plain"],
]);

type UploadState = "idle" | "ready" | "uploading" | "success" | "error";

type ApiError = {
  detail?: string | { code?: string; message?: string };
};

const ERROR_GUIDANCE: Record<string, string> = {
  no_extractable_text:
    "Belgede analiz edilebilecek metin bulunamadı. Metin içeren bir dosya yükleyin.",
  ocr_required:
    "Bu PDF taranmış görüntülerden oluşuyor. OCR uygulayıp metni aranabilir hâle getirdikten sonra yeniden yükleyin.",
  invalid_pdf:
    "PDF açılamadı. Dosyayı yeniden kaydedip tekrar yükleyin.",
  invalid_docx:
    "DOCX açılamadı. Dosyayı Word'de yeniden kaydedip tekrar yükleyin.",
  file_signature_mismatch:
    "Dosya bozuk olabilir veya uzantısı içeriğiyle eşleşmiyor. Dosyayı yeniden kaydedip tekrar yükleyin.",
};

export function validateSelectedFile(file: File): string | null {
  if (file.size === 0) {
    return "Boş dosya yüklenemez.";
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "Dosya boyutu 20 MB sınırını aşıyor.";
  }

  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  const expectedMimeType = ALLOWED_TYPES.get(extension);
  if (!expectedMimeType || file.type.toLowerCase() !== expectedMimeType) {
    return "Yalnızca PDF, DOCX ve TXT dosyaları kabul edilir.";
  }

  return null;
}

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function responseErrorMessage(xhr: XMLHttpRequest): string {
  try {
    const response = JSON.parse(xhr.responseText) as ApiError;
    if (typeof response.detail === "string") {
      return response.detail;
    }
    if (response.detail?.message) {
      return response.detail.message;
    }
    if (response.detail?.code && ERROR_GUIDANCE[response.detail.code]) {
      return ERROR_GUIDANCE[response.detail.code];
    }
  } catch {
    // A non-JSON error response is represented by the generic message below.
  }
  return "Dosya yüklenemedi. Lütfen yeniden deneyin.";
}

export function DocumentUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(null);
    setProgress(0);
    setMessage("");

    if (!file) {
      setUploadState("idle");
      return;
    }

    const validationError = validateSelectedFile(file);
    if (validationError) {
      setUploadState("error");
      setMessage(validationError);
      event.target.value = "";
      return;
    }

    setSelectedFile(file);
    setUploadState("ready");
  }

  function uploadFile() {
    if (!selectedFile || uploadState === "uploading") {
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/documents`);
    xhr.setRequestHeader("X-User-ID", DEMO_USER_ID);

    setUploadState("uploading");
    setProgress(0);
    setMessage("Dosya sunucuya gönderiliyor…");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        setProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        setProgress(100);
        setUploadState("success");
        setMessage("Belge güvenli biçimde yüklendi ve kaydedildi.");
        return;
      }

      setUploadState("error");
      setMessage(responseErrorMessage(xhr));
    };

    xhr.onerror = () => {
      setUploadState("error");
      setMessage("Sunucuya ulaşılamadı. API bağlantısını kontrol edip yeniden deneyin.");
    };

    xhr.send(formData);
  }

  function clearSelection() {
    setSelectedFile(null);
    setUploadState("idle");
    setProgress(0);
    setMessage("");
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  const isUploading = uploadState === "uploading";

  return (
    <section className="upload-section" id="belge-yukle" aria-labelledby="upload-title">
      <div className="upload-copy">
        <span className="eyebrow">Belge yükleme</span>
        <h2 id="upload-title">İncelenecek dosyayı seç</h2>
        <p>
          Dosya önce bu tarayıcıda kontrol edilir. Uygunsa güvenli depolama alanına
          gönderilir.
        </p>
        <ul className="upload-rules" aria-label="Dosya kuralları">
          <li>PDF, DOCX veya TXT</li>
          <li>En fazla 20 MB</li>
          <li>Tek seferde bir belge</li>
        </ul>
      </div>

      <div className="upload-panel">
        <label className="file-picker" htmlFor="document-file">
          <span className="file-picker-icon" aria-hidden="true">↑</span>
          <strong>{selectedFile ? "Başka dosya seç" : "Bilgisayardan dosya seç"}</strong>
          <span>Dosyayı buradan seçebilirsin</span>
        </label>
        <input
          ref={inputRef}
          className="visually-hidden"
          id="document-file"
          name="document-file"
          type="file"
          accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
          disabled={isUploading}
          onChange={selectFile}
        />

        {selectedFile && (
          <div className="selected-file">
            <div>
              <strong>{selectedFile.name}</strong>
              <span>{formatFileSize(selectedFile.size)}</span>
            </div>
            <button type="button" onClick={clearSelection} disabled={isUploading}>
              Kaldır
            </button>
          </div>
        )}

        {(isUploading || uploadState === "success") && (
          <div className="progress-block">
            <div className="progress-label">
              <span>{isUploading ? "Yükleniyor" : "Yüklendi"}</span>
              <strong>{progress}%</strong>
            </div>
            <progress max="100" value={progress} aria-label="Dosya yükleme ilerlemesi">
              {progress}%
            </progress>
          </div>
        )}

        {message && (
          <p
            className={`upload-message upload-message-${uploadState}`}
            role={uploadState === "error" ? "alert" : "status"}
          >
            {message}
          </p>
        )}

        <button
          className="upload-button"
          type="button"
          disabled={!selectedFile || isUploading || uploadState === "success"}
          onClick={uploadFile}
        >
          {isUploading ? "Yükleniyor…" : uploadState === "success" ? "Yükleme tamamlandı" : "Belgeyi yükle"}
        </button>
      </div>
    </section>
  );
}
