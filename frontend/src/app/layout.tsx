import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import Link from "next/link";
import { Briefcase, Newspaper } from "lucide-react";

export const metadata: Metadata = {
  title: "JobPrep Platform",
  description: "Automated job board + news aggregator for tech careers",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground min-h-screen flex flex-row font-sans selection:bg-spruce-green/20 selection:text-spruce-green transition-colors duration-300">
        <Providers>
          {/* Fixed Left Navigation Sidebar */}
          <aside className="w-64 fixed inset-y-0 left-0 bg-background flex flex-col z-40 border-r border-slate-soft transition-colors duration-300">
            <div className="p-8 border-b border-slate-soft">
              <Link href="/jobs" className="font-serif text-2xl font-semibold text-slate-ink hover:text-spruce-green transition-colors">
                JobPrep
              </Link>
            </div>
            
            <nav className="flex-1 px-4 py-8 space-y-2">
              <Link 
                href="/jobs" 
                className="flex items-center gap-3 px-4 py-3 text-foreground hover:bg-slate-soft/30 hover:text-spruce-green rounded-md transition-colors font-sans text-sm font-medium group"
              >
                <Briefcase size={18} className="text-slate-ink/70 group-hover:text-spruce-green transition-colors" />
                Jobs
              </Link>
              <Link 
                href="/news" 
                className="flex items-center gap-3 px-4 py-3 text-foreground hover:bg-slate-soft/30 hover:text-spruce-green rounded-md transition-colors font-sans text-sm font-medium group"
              >
                <Newspaper size={18} className="text-slate-ink/70 group-hover:text-spruce-green transition-colors" />
                News
              </Link>
            </nav>

            {/* Bottom section */}
            <div className="p-6 border-t border-slate-soft">
              <p className="font-mono text-xs text-slate-ink/50 uppercase tracking-widest text-center">v1.0.0</p>
            </div>
          </aside>

          {/* Main Content Area */}
          <main className="flex-grow ml-64 min-h-screen bg-background transition-colors duration-300">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
