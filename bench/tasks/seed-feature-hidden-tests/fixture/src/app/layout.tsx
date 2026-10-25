import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "tabby",
  description: "Shared trip expenses",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="logo">
            tabby
          </Link>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
