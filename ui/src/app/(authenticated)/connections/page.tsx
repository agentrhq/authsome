"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

import { ConnectionsView } from "@/components/authsome-dashboard";
import { fetchDashboard } from "@/lib/authsome-api";

function ConnectionsContent() {
  const searchParams = useSearchParams();
  const providerFilter = searchParams.get("provider") ?? "";
  const { data, mutate } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return (
    <ConnectionsView
      connections={data.connections}
      globalConnections={data.globalConnections}
      initialFilter={providerFilter}
      isAdmin={data.account.isAdmin}
      key={providerFilter}
      onRefresh={() => void mutate()}
    />
  );
}

export default function ConnectionsPage() {
  return (
    <Suspense fallback={null}>
      <ConnectionsContent />
    </Suspense>
  );
}
