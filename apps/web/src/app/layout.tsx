import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "İntihal Prototype",
    template: "%s | İntihal Prototype",
  },
  description:
    "Belgeleri izinli kaynaklarla karşılaştıran açıklanabilir benzerlik sistemi.",
};

type RootLayoutProps = Readonly<{
  children: ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="tr">
      <body>
        <div className="site-shell">
          <header className="site-header">
            <Link className="brand" href="/" aria-label="İntihal Prototype ana sayfa">
              <span className="brand-mark" aria-hidden="true">
                İP
              </span>
              <span>
                <strong>İntihal Prototype</strong>
                <small>Doküman Benzerlik Sistemi</small>
              </span>
            </Link>

            <span className="status-badge">
              <span className="status-dot" aria-hidden="true" />
              MVP geliştiriliyor
            </span>
          </header>

          <main>{children}</main>

          <footer className="site-footer">
            <p>Benzerlik bulguları tek başına intihal kararı değildir.</p>
            <span>v0.1.0 MVP</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
