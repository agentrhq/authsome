"use client";

import { Suspense, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LogOut } from "lucide-react";
import useSWR from "swr";

import {
  AppSidebar,
  ErrorState,
  LoadingScreen,
  View,
  currentBrowserPath,
  isUnauthorized,
} from "@/components/authsome-dashboard";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { DashboardData, fetchDashboard, ProviderView } from "@/lib/authsome-api";

type CrumbItem = { label: string; href?: string };

function pathToView(pathname: string): View {
  const first = pathname.split("/").filter(Boolean)[0] ?? "";
  const map: Record<string, View> = {
    providers: "providers",
    connections: "connections",
    agents: "agents",
    principal: "principals",
    vault: "vault",
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
    principal: "Principals",
    vault: "Vault",
    audit: "Audit Log",
    settings: "Settings",
  };

  if (!first) return [{ label: "Dashboard" }];

  const parent = navLabel[first];
  if (!parent) return [{ label: "Dashboard", href: "/" }];

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
            <>
              {i > 0 && <BreadcrumbSeparator key={`sep-${i}`} />}
              <BreadcrumbItem key={i}>
                {isLast ? (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink render={<Link href={crumb.href!} />}>
                    {crumb.label}
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </>
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

  return (
    <SidebarProvider className="h-svh overflow-hidden">
      <AppSidebar activeView={activeView} data={data} />
      <SidebarInset className="min-h-0">
        <header className="flex min-h-14 items-center gap-2 border-b bg-card px-4 py-3 md:px-6">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-1 h-4" />
          <Suspense fallback={<Skeleton className="h-4 w-32" />}>
            <AppBreadcrumb data={data} />
          </Suspense>
          <div className="ml-auto">
            <form action="/api/logout" method="post">
              <input name="return_url" type="hidden" value="/" />
              <Button size="sm" type="submit" variant="ghost">
                <LogOut />
                Sign out
              </Button>
            </form>
          </div>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid w-full max-w-[86rem] gap-6 p-4 md:p-6">
            {children}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
