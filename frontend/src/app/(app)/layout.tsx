import DashboardNavbar from "@/components/DashboardNavbar";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <DashboardNavbar />
      <main className="flex-1 w-full bg-background transition-colors duration-200">
        {children}
      </main>
    </div>
  );
}
