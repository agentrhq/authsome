"use client";

import useSWR from "swr";

import { ProvidersView } from "@/components/dashboard/provider-views";
import { fetchDashboard } from "@/lib/authsome-api";

export default function ProvidersPage() {
  const { data, mutate } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return (
    <ProvidersView
      isAdmin={data.account.isAdmin}
      onRefresh={() => void mutate()}
      providers={data.providers}
    />
  );
}
