import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import Providers from "./providers";
import { SITE_URL } from "@/lib/urls";

// Self-hosted, not next/font/google: avoids build-time network fetches.
// Two fonts only: Plus Jakarta Sans (UI & display) + Fira Code (tabular data & tags).
const plusJakarta = localFont({
  src: [{ path: "./fonts/plus-jakarta-sans-var.woff2", weight: "200 800", style: "normal" }],
  variable: "--font-jakarta",
  display: "swap",
});

const firaCode = localFont({
  src: [{ path: "./fonts/fira-code-var.woff2", weight: "300 700", style: "normal" }],
  variable: "--font-fira",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "JobPrep — Software engineering internships in one feed",
  description: "Hourly software engineering internship feed and daily tech news",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${plusJakarta.variable} ${firaCode.variable}`}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var stored = localStorage.getItem('jobprep_theme');
                  var isDark = stored ? stored === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
                  if (isDark) {
                    document.documentElement.classList.add('dark');
                  } else {
                    document.documentElement.classList.remove('dark');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body
        suppressHydrationWarning
        className="bg-surface text-on-surface min-h-screen font-sans selection:bg-primary/20 selection:text-primary transition-colors duration-200"
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
