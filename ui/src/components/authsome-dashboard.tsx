"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import useSWR from "swr";

import { ConnectionsView } from "@/components/dashboard/connection-views";
import { currentBrowserPath, isUnauthorized } from "@/components/dashboard/dashboard-routing";
import {
  AppSidebar,
  ErrorState,
  LoadingScreen,
  Topbar,
  isDashboardView,
} from "@/components/dashboard/dashboard-shell";
import type { View } from "@/components/dashboard/dashboard-shell";
import { AgentsView, AuditView, DashboardView, PrincipalsView } from "@/components/dashboard/overview-views";
import { ProvidersView } from "@/components/dashboard/provider-views";
import { SettingsView } from "@/components/dashboard/settings-view";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { DashboardData, fetchDashboard } from "@/lib/authsome-api";

export {
  AuthsomeClaim,
  AuthsomeClaimFromUrl,
  AuthsomeLogin,
  AuthsomeSessionDeviceFromUrl,
  AuthsomeSessionInputFromUrl,
  AuthsomeSessionSuccessFromUrl,
} from "@/components/dashboard/auth-flows";
export {
  AuthsomeConnectionDetail,
  AuthsomeConnectionDetailRoute,
  ConnectionDetailBody,
} from "@/components/dashboard/connection-detail-view";
export { ConnectionsView } from "@/components/dashboard/connection-views";
export { currentBrowserPath, isUnauthorized } from "@/components/dashboard/dashboard-routing";
export {
  AppSidebar,
  DashboardDetailShell,
  ErrorState,
  LoadingScreen,
} from "@/components/dashboard/dashboard-shell";
export type { View } from "@/components/dashboard/dashboard-shell";
export {
  AgentsView,
  AuditView,
  DashboardView,
  PrincipalsView,
} from "@/components/dashboard/overview-views";
export {
  AuthsomeProviderDetail,
  AuthsomeProviderDetailRoute,
  ProviderDetailBody,
} from "@/components/dashboard/provider-detail-view";
export { ProvidersView } from "@/components/dashboard/provider-views";
export { SettingsView } from "@/components/dashboard/settings-view";

function ActiveView({
  connectionFilter,
  data,
  onRefresh,
  view,
}: {
  connectionFilter?: string;
  data: DashboardData;
  onRefresh: () => void;
  view: View;
}) {
  if (view === "providers") {
    return <ProvidersView isAdmin={data.account.isAdmin} onRefresh={onRefresh} providers={data.providers} />;
  }
  if (view === "connections") {
    return (
      <ConnectionsView
        connections={data.connections}
        globalConnections={data.globalConnections}
        initialFilter={connectionFilter}
        isAdmin={data.account.isAdmin}
        onRefresh={onRefresh}
      />
    );
  }
  if (view === "agents") return <AgentsView data={data} />;
  if (view === "principals") return <PrincipalsView />;
  if (view === "audit") return <AuditView data={data} />;
  if (view === "settings") return <SettingsView data={data} />;
  return <DashboardView data={data} />;
}

export function AuthsomeDashboard({ connectionFilter, view = "dashboard" }: { connectionFilter?: string; view?: View }) {
  const pathname = usePathname();
  const router = useRouter();
  const activeView = isDashboardView(view) ? view : "dashboard";
  const { data, error, mutate } = useSWR("authsome-dashboard", fetchDashboard, {
    dedupingInterval: 10_000,
    revalidateOnFocus: true,
  });

  useEffect(() => {
    if (isUnauthorized(error)) {
      router.replace(`/login?next=${encodeURIComponent(currentBrowserPath(pathname || "/"))}`);
    }
  }, [error, pathname, router]);

  if (isUnauthorized(error)) return <LoadingScreen />;
  if (error) return <ErrorState onRetry={() => void mutate()} />;
  if (!data) return <LoadingScreen />;

  return (
    <SidebarProvider className="h-svh overflow-hidden">
      <AppSidebar activeView={activeView} data={data} />
      <SidebarInset className="min-h-0">
        <Topbar />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid w-full max-w-[86rem] gap-6 p-4 md:p-6">
            <ActiveView
              connectionFilter={connectionFilter}
              data={data}
              onRefresh={() => void mutate()}
              view={activeView}
            />
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
