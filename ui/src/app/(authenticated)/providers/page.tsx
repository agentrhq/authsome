"use client";

import useSWR from "swr";

import { ProvidersView } from "@/components/dashboard/provider-views";
import { fetchDashboard } from "@/lib/authsome-api";

export default function ProvidersPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <ProvidersView providers={data.providers} />;
}
