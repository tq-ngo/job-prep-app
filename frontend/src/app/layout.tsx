import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Lora, Fira_Code } from "next/font/google";
import "./globals.css";
import Providers from "./providers";
import { SITE_URL } from "@/lib/urls";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-jakarta",
  display: "swap",
});

const lora = Lora({
  subsets: ["latin"],
  variable: "--font-lora",
  display: "swap",
  // The hero headline uses italic; declaring it loads the real italic face
  // instead of a synthesized slant that swaps in late.
  style: ["normal", "italic"],
});

// Mono is only used for small labels and pills, never above the fold's
// largest text, so it isn't worth a preload slot competing with the LCP.
const firaCode = Fira_Code({
  subsets: ["latin"],
  variable: "--font-fira",
  display: "swap",
  weight: ["400", "500"],
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
