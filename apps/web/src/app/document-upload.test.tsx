import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  DocumentUpload,
  responseErrorMessage,
  validateSelectedFile,
} from "./document-upload";

class MockXMLHttpRequest {
  static latest: MockXMLHttpRequest;
  withCredentials = false;
  status = 0;
  responseText = "";
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  open = vi.fn();
  setRequestHeader = vi.fn();
  send = vi.fn();

  constructor() {
    MockXMLHttpRequest.latest = this;
  }
}

describe("DocumentUpload", () => {
  beforeEach(() => {
    vi.stubGlobal("XMLHttpRequest", MockXMLHttpRequest);
  });

  it("rejects files over 20 MB before upload", () => {
    const oversized = new File([new Uint8Array(20 * 1024 * 1024 + 1)], "tez.pdf", {
      type: "application/pdf",
    });

    expect(validateSelectedFile(oversized)).toMatch(/20 MB sınırını aşıyor/i);
  });

  it("rejects an extension and MIME mismatch", () => {
    const fakePdf = new File(["plain text"], "tez.pdf", { type: "text/plain" });

    expect(validateSelectedFile(fakePdf)).toMatch(/yalnızca PDF, DOCX ve TXT/i);
  });

  it("shows the selected file and real upload progress", () => {
    render(<DocumentUpload />);
    const input = screen.getByLabelText(/bilgisayardan dosya seç/i);
    const file = new File(["tez içeriği"], "tez.txt", { type: "text/plain" });

    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByText("tez.txt")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /belgeyi yükle/i }));
    const request = MockXMLHttpRequest.latest;
    expect(request.open).toHaveBeenCalledWith(
      "POST",
      "http://localhost:8000/api/v1/documents",
    );
    expect(request.setRequestHeader).toHaveBeenCalledWith(
      "X-CSRF-Protection",
      "1",
    );

    expect(request.withCredentials).toBe(true);

    act(() => {
      request.upload.onprogress?.(
        new ProgressEvent("progress", { lengthComputable: true, loaded: 3, total: 4 }),
      );
    });
    expect(screen.getByRole("progressbar")).toHaveValue(75);

    request.status = 201;
    act(() => request.onload?.());
    expect(screen.getByText(/güvenli biçimde yüklendi/i)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveValue(100);
  });

  it("returns to login when the upload session expires", () => {
    const expired = vi.fn();
    render(<DocumentUpload onSessionExpired={expired} />);
    fireEvent.change(screen.getByLabelText(/bilgisayardan dosya seç/i), {
      target: { files: [new File(["text"], "test.txt", { type: "text/plain" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: /belgeyi yükle/i }));
    MockXMLHttpRequest.latest.status = 401;
    act(() => MockXMLHttpRequest.latest.onload?.());
    expect(expired).toHaveBeenCalledOnce();
  });

  it.each(["7", "30"])("sends the selected %s day retention window", (days) => {
    render(<DocumentUpload />);
    fireEvent.change(screen.getByLabelText("Belge saklama süresi"), { target: { value: days } });
    fireEvent.change(screen.getByLabelText(/bilgisayardan dosya seç/i), {
      target: { files: [new File(["text"], "test.txt", { type: "text/plain" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: /belgeyi yükle/i }));
    const body = MockXMLHttpRequest.latest.send.mock.calls[0][0] as FormData;
    expect(body.get("retention_days")).toBe(days);
    expect(screen.getByLabelText("Belge saklama süresi")).toBeDisabled();
  });

  it.each([
    ["no_extractable_text", /analiz edilebilecek metin bulunamadı/i],
    ["ocr_required", /OCR uygulayıp metni aranabilir/i],
    ["invalid_pdf", /PDF açılamadı.*yeniden kaydedip/i],
    ["invalid_docx", /DOCX açılamadı.*Word'de yeniden kaydedip/i],
    ["file_signature_mismatch", /dosya bozuk olabilir/i],
  ])("explains the %s error with an action", (code, expectedMessage) => {
    const request = {
      responseText: JSON.stringify({ detail: { code } }),
    } as XMLHttpRequest;

    expect(responseErrorMessage(request)).toMatch(expectedMessage);
  });
});
