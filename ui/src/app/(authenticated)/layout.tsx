"use client";

import React, { Suspense, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LogOut } from "lucide-react";
import useSWR from "swr";

import { currentBrowserPath, isUnauthorized } from "@/components/dashboard/dashboard-routing";
import {
  AppSidebar,
  ErrorState,
  LoadingScreen,
} from "@/components/dashboard/dashboard-shell";
import type { View } from "@/components/dashboard/dashboard-shell";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { DashboardData, fetchDashboard, ProviderView } from "@/lib/authsome-api";
import { cn } from "@/lib/utils";

type CrumbItem = { label: string; href?: string };

function pathToView(pathname: string): View {
  const first = pathname.split("/").filter(Boolean)[0] ?? "";
  const map: Record<string, View> = {
    providers: "providers",
    connections: "connections",
    agents: "agents",
    audit: "audit",
    settings: "settings",
  };
  return map[first] ?? "dashboard";
}

function buildBreadcrumbs(
  pathname: string,
  searchParams: URLSearchParams,
  data: DashboardData,
): CrumbItem[] {
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];

  const navLabel: Record<string, string> = {
    providers: "Providers",
    connections: "Connections",
    agents: "Agents",
    audit: "Audit Log",
    settings: "Settings",
    principal: "Principals",
  };

  const settingsSubLabel: Record<string, string> = {
    general: "General",
    security: "Security",
    about: "About",
    principals: "Principals",
  };

  if (!first) return [{ label: "Dashboard" }];

  const parent = navLabel[first];
  if (!parent) return [{ label: "Dashboard", href: "/" }];

  if (first === "settings" && segments[1] && settingsSubLabel[segments[1]]) {
    return [
      { label: "Settings", href: "/settings" },
      { label: settingsSubLabel[segments[1]] },
    ];
  }

  const isDetail = segments[1] === "detail";
  if (!isDetail) return [{ label: parent }];

  const parentHref = `/${first}`;

  if (first === "providers") {
    const providerName = searchParams.get("provider") ?? "";
    const provider = data.providers.find((p: ProviderView) => p.name === providerName);
    return [
      { label: parent, href: parentHref },
      { label: provider?.displayName ?? providerName ?? "Detail" },
    ];
  }

  if (first === "connections") {
    const connectionName = searchParams.get("connection") ?? "";
    const providerName = searchParams.get("provider") ?? "";
    const provider = data.providers.find((p: ProviderView) => p.name === providerName);
    const parentLabel = provider ? `${parent} · ${provider.displayName}` : parent;
    return [
      { label: parentLabel, href: parentHref },
      { label: connectionName || "Detail" },
    ];
  }

  return [{ label: parent }];
}

function AppBreadcrumb({ data }: { data: DashboardData }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const crumbs = buildBreadcrumbs(pathname, new URLSearchParams(searchParams.toString()), data);

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <React.Fragment key={crumb.href ?? crumb.label}>
              {i > 0 && <BreadcrumbSeparator />}
              <BreadcrumbItem>
                {isLast ? (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink render={<Link href={crumb.href!} />}>
                    {crumb.label}
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </React.Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data, error, mutate } = useSWR("authsome-dashboard", fetchDashboard, {
    dedupingInterval: 10_000,
    revalidateOnFocus: true,
  });

  useEffect(() => {
    if (isUnauthorized(error)) {
      router.replace(`/login?next=${encodeURIComponent(currentBrowserPath(pathname ?? "/"))}`);
    }
  }, [error, pathname, router]);

  if (isUnauthorized(error) || !data) return <LoadingScreen />;
  if (error) return <ErrorState onRetry={() => void mutate()} />;

  const activeView = pathToView(pathname);
  const isSettingsRoute = pathname.startsWith("/settings");

  return (
    <SidebarProvider className="h-svh overflow-hidden">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <AppSidebar activeView={activeView} data={data} />
      <SidebarInset className="min-h-0">
        <header
          className="flex h-14 shrink-0 items-center justify-between border-b bg-background/60 px-4 backdrop-blur-sm"
          role="banner"
        >
          <div className="flex items-center gap-2">
            <SidebarTrigger className="-ml-1" />
            <span className="mx-1 hidden h-5 w-px bg-border md:block" aria-hidden="true" />
            <Suspense fallback={<Skeleton className="h-5 w-36" />}>
              <AppBreadcrumb data={data} />
            </Suspense>
          </div>
          <div className="flex items-center gap-1">
            <form action="/api/logout" method="post" aria-label="Sign out">
              <input name="return_url" type="hidden" value="/" />
              <Button size="default" type="submit" variant="ghost" className="text-muted-foreground hover:text-foreground">
                <LogOut className="size-4" />
                <span className="hidden sm:inline">Sign out</span>
              </Button>
            </form>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto" id="main-content">
          <div
            className={cn(
              "grid w-full gap-5",
              isSettingsRoute ? "min-h-full" : "mx-auto max-w-[86rem] p-4",
            )}
          >
            {children}
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
