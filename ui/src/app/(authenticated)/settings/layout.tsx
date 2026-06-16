"use client";

import { Info, Settings2, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import useSWR from "swr";

import { cn } from "@/lib/utils";
import { fetchDashboard } from "@/lib/authsome-api";

type SettingsNavItem = {
  href: string;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
};

const SETTINGS_NAV: SettingsNavItem[] = [
  { href: "/settings/general", label: "General", icon: <Settings2 className="size-4" /> },
  { href: "/settings/principals", label: "Principals", icon: <Users className="size-4" />, adminOnly: true },
  { href: "/settings/security", label: "Security", icon: <ShieldCheck className="size-4" /> },
  { href: "/settings/about", label: "About", icon: <Info className="size-4" /> },
];

export default function SettingsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { data } = useSWR("authsome-dashboard", fetchDashboard);

  const items = SETTINGS_NAV.filter((item) => !item.adminOnly || data?.account.isAdmin);

  return (
    <div className="-ml-4 md:-ml-6 flex gap-4 min-h-full">
      <nav className="w-40 shrink-0 border-r pl-4 md:pl-6 pr-3">
        <ul className="grid gap-px">
          {items.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
                  )}
                >
                  {item.icon}
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="flex-1 min-w-0">
        {children}
      </div>
    </div>
  );
}
