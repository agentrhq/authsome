"use client";

import useSWR from "swr";

import { ConnectionsView } from "@/components/authsome-dashboard";
import { fetchDashboard } from "@/lib/authsome-api";

export default function ConnectionsPage() {
  const { data, mutate } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return (
    <ConnectionsView
      connections={data.connections}
      globalConnections={data.globalConnections}
      isAdmin={data.account.isAdmin}
      onRefresh={() => void mutate()}
    />
  );
}
