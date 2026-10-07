import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthPanel } from "./auth-panel";

const USER = { id: "person", email: "person@example.com", display_name: "Person", role: "user" };
const reply = (status: number, body: unknown = {}) => ({ ok: status < 400, status, json: async () => body });

function fillLogin() {
  fireEvent.change(screen.getByLabelText("E-posta"), { target: { value: USER.email } });
  fireEvent.change(screen.getByLabelText("Parola"), { target: { value: "correct horse battery staple" } });
}

describe("AuthPanel", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("hides upload until authenticated, logs in with cookie credentials, and logs out", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(401))
      .mockResolvedValueOnce(reply(200, USER)).mockResolvedValueOnce(reply(204));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthPanel />);
    await screen.findByRole("button", { name: "Giriş yap" });
    expect(screen.queryByLabelText(/bilgisayardan dosya seç/i)).not.toBeInTheDocument();
    fillLogin();
    fireEvent.click(screen.getByRole("button", { name: "Giriş yap" }));
    await screen.findByLabelText(/bilgisayardan dosya seç/i);
    expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining("/auth/login"), expect.objectContaining({
      credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Protection": "1" },
    }));
    fireEvent.click(screen.getByRole("button", { name: "Çıkış yap" }));
    await screen.findByRole("button", { name: "Giriş yap" });
    expect(screen.queryByLabelText(/bilgisayardan dosya seç/i)).not.toBeInTheDocument();
  });

  it("registers an ordinary user then asks them to log in", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(reply(401)).mockResolvedValueOnce(reply(201, USER));
    vi.stubGlobal("fetch", fetchMock);
    render(<AuthPanel />);
    fireEvent.click(await screen.findByRole("button", { name: "Yeni hesap oluştur" }));
    fillLogin();
    fireEvent.change(screen.getByLabelText("Adınız"), { target: { value: "Person" } });
    fireEvent.click(screen.getByRole("button", { name: "Hesap oluştur" }));
    await screen.findByText(/hesabınız oluşturuldu/i);
    const body = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(body.display_name).toBe("Person");
    expect(body.role).toBeUndefined();
    expect(screen.queryByLabelText(/bilgisayardan dosya seç/i)).not.toBeInTheDocument();
  });

  it("restores a session and retains it when logout fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(reply(200, USER)).mockResolvedValueOnce(reply(500)));
    render(<AuthPanel />);
    await screen.findByLabelText(/bilgisayardan dosya seç/i);
    fireEvent.click(screen.getByRole("button", { name: "Çıkış yap" }));
    await screen.findByText(/çıkış yapılamadı/i);
    await waitFor(() => expect(screen.getByRole("button", { name: "Çıkış yap" })).not.toBeDisabled());
    expect(screen.getByLabelText(/bilgisayardan dosya seç/i)).toBeInTheDocument();
  });
});
