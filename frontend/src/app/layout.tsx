import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import Providers from "./providers";
import { SITE_URL } from "@/lib/urls";

// Self-hosted, not next/font/google: that downloads the fonts from Google
// at BUILD time, so every build depended on fonts.googleapis.com, and CI
// builds failed when Google throttled or refused the runner. The files in
// ./fonts are the OFL variable fonts from github.com/google/fonts, subset
// to Latin + Latin Extended (accented names like "Łódź" stay in-font) and
// converted to WOFF2. Licences sit alongside them.

const plusJakarta = localFont({
  src: [{ path: "./fonts/plus-jakarta-sans-var.woff2", weight: "200 800", style: "normal" }],
  variable: "--font-jakarta",
  display: "swap",
});

const lora = localFont({
  // The hero headline uses italic; declaring it loads the real italic face
  // instead of a synthesized slant that swaps in late.
  src: [
    { path: "./fonts/lora-var.woff2", weight: "400 700", style: "normal" },
    { path: "./fonts/lora-italic-var.woff2", weight: "400 700", style: "italic" },
  ],
  variable: "--font-lora",
  display: "swap",
});

// Mono is only used for small labels and pills, never above the fold's
// largest text, so it isn't worth a preload slot competing with the LCP.
const firaCode = localFont({
  src: [{ path: "./fonts/fira-code-var.woff2", weight: "300 700", style: "normal" }],
  variable: "--font-fira",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  // Resolves relative metadata URLs (og:url "/", the generated og:image).
  // Without it Next fell back to localhost in production previews.
  metadataBase: new URL(SITE_URL),
  title: "JobPrep - Automated Tech Career Center",
  description: "Automated job board + news aggregator for tech careers",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${plusJakarta.variable} ${lora.variable} ${firaCode.variable}`}
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
        className="bg-background text-foreground min-h-screen font-sans selection:bg-spruce-green/20 selection:text-spruce-green transition-colors duration-200"
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
