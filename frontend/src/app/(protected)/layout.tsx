"use client";

import Sidebar from "@/components/Sidebar";
import AuthGuard from "@/components/AuthGuard";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex flex-row min-h-screen">
        <Sidebar />
        <main className="flex-grow ml-64 min-h-screen bg-background transition-colors duration-300">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
