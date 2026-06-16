"use client";

import { Info, Settings2, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import useSWR from "swr";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { fetchDashboard } from "@/lib/authsome-api";

type SettingsNavItem = {
  href: string;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
};

const SETTINGS_NAV: SettingsNavItem[] = [
  { href: "/settings/general", label: "General", icon: <Settings2 /> },
  { href: "/settings/principals", label: "Principals", icon: <Users />, adminOnly: true },
  { href: "/settings/security", label: "Security", icon: <ShieldCheck /> },
  { href: "/settings/about", label: "About", icon: <Info /> },
];

export default function SettingsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { data } = useSWR("authsome-dashboard", fetchDashboard);

  const items = SETTINGS_NAV.filter((item) => !item.adminOnly || data?.account.isAdmin);

  return (
    <div className="-my-4 -mr-4 flex min-h-full">
      <Sidebar
        collapsible="none"
        className="w-44 border-r"
        style={{ "--sidebar-width": "11rem" } as React.CSSProperties}
      >
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Settings</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {items.map((item) => (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      render={<Link href={item.href} />}
                      isActive={pathname === item.href || pathname.startsWith(item.href + "/")}
                    >
                      {item.icon}
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>
      <div className="flex-1 min-w-0 p-4">
        {children}
      </div>
    </div>
  );
}
