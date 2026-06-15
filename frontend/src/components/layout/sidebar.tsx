"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Briefcase, LayoutDashboard, Code2, Newspaper, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { Separator } from "@/components/ui/separator";

const routes = [
  {
    label: "Dashboard",
    icon: LayoutDashboard,
    href: "/dashboard",
    color: "text-sky-500",
  },
  {
    label: "Jobs",
    icon: Briefcase,
    href: "/jobs",
    color: "text-violet-500",
  },
  {
    label: "LeetCode",
    icon: Code2,
    href: "/leetcode",
    color: "text-orange-500",
  },
  {
    label: "News",
    icon: Newspaper,
    href: "/news",
    color: "text-emerald-500",
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { logout, user } = useAuth();

  return (
    <div className="space-y-4 py-4 flex flex-col h-full bg-[#111827] text-white w-64 hidden md:flex">
      <div className="px-3 py-2 flex-1">
        <Link href="/dashboard" className="flex items-center pl-3 mb-14">
          <h1 className="text-2xl font-bold">JobPrep</h1>
        </Link>
        <div className="space-y-1">
          {routes.map((route) => (
            <Link
              key={route.href}
              href={route.href}
              className={cn(
                "text-sm group flex p-3 w-full justify-start font-medium cursor-pointer hover:text-white hover:bg-white/10 rounded-lg transition",
                pathname === route.href ? "text-white bg-white/10" : "text-zinc-400"
              )}
            >
              <div className="flex items-center flex-1">
                <route.icon className={cn("h-5 w-5 mr-3", route.color)} />
                {route.label}
              </div>
            </Link>
          ))}
        </div>
      </div>
      <div className="px-3 py-2 border-t border-zinc-700">
        <div className="flex items-center gap-x-2 px-3 py-2 mb-2">
          <div className="bg-zinc-700 h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold uppercase">
            {user?.email[0]}
          </div>
          <div className="flex flex-col truncate">
            <span className="text-sm font-medium truncate">{user?.email}</span>
          </div>
        </div>
        <Button
          variant="ghost"
          className="w-full justify-start text-zinc-400 hover:text-white hover:bg-white/10"
          onClick={() => logout()}
        >
          <LogOut className="h-5 w-5 mr-3" />
          Logout
        </Button>
      </div>
    </div>
  );
}
