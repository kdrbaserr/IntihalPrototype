"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { DocumentUpload } from "./document-upload";

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
type User = { id: string; email: string; display_name: string; role: "user" | "admin" };

export function AuthPanel() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const sessionExpired = useCallback(() => {
    setUser(null);
    setMessage("Oturumunuz sona erdi. Yeniden giriş yapın.");
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API}/auth/me`, { credentials: "include", signal: controller.signal })
      .then(async (response) => {
        if (response.ok) setUser(await response.json());
        else if (response.status !== 401) setMessage("Oturum kontrol edilemedi. Yeniden giriş yapın.");
      })
      .catch(() => { if (!controller.signal.aborted) setMessage("Sunucuya ulaşılamadı."); })
      .finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${API}/auth/${register ? "register" : "login"}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Protection": "1" },
        body: JSON.stringify({ email: data.get("email"), password: data.get("password"),
          ...(register ? { display_name: data.get("display_name") } : {}) }),
      });
      const result = await response.json();
      if (!response.ok) {
        setMessage(result.detail?.message ?? "Bilgilerinizi kontrol edip yeniden deneyin.");
      } else if (register) {
        form.reset();
        setRegister(false);
        setMessage("Hesabınız oluşturuldu. Giriş yapabilirsiniz.");
      } else {
        form.reset();
        setUser(result);
      }
    } catch { setMessage("Sunucuya ulaşılamadı."); }
    finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${API}/auth/logout`, {
        method: "POST", credentials: "include", headers: { "X-CSRF-Protection": "1" },
      });
      if (!response.ok) throw new Error("logout failed");
      setUser(null);
    } catch { setMessage("Çıkış yapılamadı. Yeniden deneyin."); }
    finally { setBusy(false); }
  }

  if (checking) return <p role="status">Oturum kontrol ediliyor…</p>;
  return <>
    <section className="auth-panel" id={user ? undefined : "belge-yukle"} aria-label="Kullanıcı hesabı">
      {user ? <>
        <p>{user.display_name} · {user.role === "admin" ? "Yönetici" : "Kullanıcı"}</p>
        <button type="button" onClick={logout} disabled={busy}>Çıkış yap</button>
      </> : <>
        <h2>{register ? "Hesap oluştur" : "Giriş yap"}</h2>
        <p>Belge yüklemek ve analiz etmek için hesabınıza giriş yapın.</p>
        <form onSubmit={submit}>
          {register && <label>Adınız<input name="display_name" required maxLength={200} autoComplete="name" /></label>}
          <label>E-posta<input name="email" type="email" required maxLength={320} autoComplete="username" /></label>
          <label>Parola<input name="password" type="password" required minLength={register ? 15 : 1}
            maxLength={128} autoComplete={register ? "new-password" : "current-password"} /></label>
          {register && <p>Parolanız 15–128 karakter olmalı.</p>}
          <button className="upload-button" disabled={busy}>{busy ? "İşleniyor…" : register ? "Hesap oluştur" : "Giriş yap"}</button>
        </form>
        <button type="button" disabled={busy} onClick={() => { setRegister(!register); setMessage(""); }}>
          {register ? "Giriş ekranına dön" : "Yeni hesap oluştur"}
        </button>
      </>}
      {message && <p role="status">{message}</p>}
    </section>
    {user && <DocumentUpload key={user.id} onSessionExpired={sessionExpired} />}
  </>;
}
