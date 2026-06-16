"use client";

import {
  AppWindow,
  BookOpen,
  CircleAlert,
  ClipboardList,
  GitBranch,
  KeyRound,
  LifeBuoy,
  Link2,
  LogOut,
  Settings,
  UserRound,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { ReactNode } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { DashboardData } from "@/lib/authsome-api";

export type View = "dashboard" | "providers" | "connections" | "agents" | "audit" | "settings";

type NavItem = {
  id: View;
  href: string;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
};

export const NAV_ITEMS: NavItem[] = [
  { id: "dashboard", href: "/", label: "Dashboard", icon: <AppWindow /> },
  { id: "providers", href: "/providers", label: "Providers", icon: <KeyRound /> },
  { id: "connections", href: "/connections", label: "Connections", icon: <Link2 /> },
  { id: "agents", href: "/agents", label: "Agents", icon: <UserRound /> },
  { id: "audit", href: "/audit", label: "Audit Log", icon: <ClipboardList /> },
  { id: "settings", href: "/settings", label: "Settings", icon: <Settings /> },
];

const NEXT_URL = "/";

export function isDashboardView(view: string): view is View {
  return NAV_ITEMS.some((item) => item.id === view);
}

export function LoadingScreen() {
  return (
    <SidebarProvider>
      <Sidebar collapsible="offcanvas">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <Skeleton className="h-9 w-full rounded-md" />
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {Array.from({ length: 7 }).map((_, i) => (
                  <SidebarMenuSkeleton key={i} showIcon />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>
      <SidebarInset>
        <header className="flex h-14 items-center border-b px-4">
          <Skeleton className="size-8 rounded-md" />
        </header>
        <section className="p-6">
          <Skeleton className="h-10 w-56" />
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton className="h-32 rounded-lg" key={i} />
            ))}
          </div>
        </section>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-start gap-2">
            <CircleAlert className="mt-0.5 size-5 shrink-0 text-destructive" />
            <span>Dashboard Unavailable</span>
          </CardTitle>
          <CardDescription>The local daemon is not reachable. Start it again, then retry.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={onRetry} type="button">
            Retry
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}

export function DashboardDetailShell({
  activeView,
  children,
  data,
}: {
  activeView: View;
  children: ReactNode;
  data: DashboardData;
}) {
  return (
    <SidebarProvider className="h-svh overflow-hidden">
      <AppSidebar activeView={activeView} data={data} />
      <SidebarInset className="min-h-0">
        <Topbar />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid w-full max-w-[86rem] gap-5 py-4 pr-4">
            {children}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function AppSidebar({
  activeView,
  data,
}: {
  activeView: View;
  data: DashboardData;
}) {
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || data.account.isAdmin);

  return (
    <Sidebar collapsible="offcanvas">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link href="/" />}>
              <Image alt="Authsome" className="size-5 shrink-0" height={20} src="/logo.svg" width={20} />
              <span className="font-semibold">Authsome</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    render={<Link href={item.href} />}
                    isActive={activeView === item.id}
                    tooltip={item.label}
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
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton render={<Link href="https://authsome.ai/docs" rel="noreferrer" target="_blank" />}>
              <BookOpen />
              <span>Docs</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton render={<Link href="https://github.com/agentrhq/authsome" rel="noreferrer" target="_blank" />}>
              <GitBranch />
              <span>GitHub</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton render={<Link href="https://authsome.ai/support" rel="noreferrer" target="_blank" />}>
              <LifeBuoy />
              <span>Support</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarSeparator />
        <div className="flex items-center justify-between px-2 py-1">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{data.account.email || data.account.agent}</div>
            {data.account.roleLabel ? (
              <div className="mt-0.5 text-xs text-muted-foreground">{data.account.roleLabel}</div>
            ) : null}
          </div>
          <ThemeToggle />
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

export function Topbar() {
  return (
    <header
      className="flex h-14 shrink-0 items-center justify-between border-b bg-background/60 px-4 backdrop-blur-sm"
      role="banner"
    >
      <SidebarTrigger className="-ml-1" />
      <div className="flex items-center gap-1">
        <form action="/api/logout" method="post" aria-label="Sign out">
          <input name="return_url" type="hidden" value={NEXT_URL} />
          <Button size="default" type="submit" variant="ghost" className="text-muted-foreground hover:text-foreground">
            <LogOut className="size-4" />
            <span className="hidden sm:inline">Sign out</span>
          </Button>
        </form>
      </div>
    </header>
  );
}
