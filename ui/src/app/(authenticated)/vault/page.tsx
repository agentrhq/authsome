"use client";

import useSWR from "swr";

import { VaultView } from "@/components/authsome-dashboard";
import { fetchDashboard } from "@/lib/authsome-api";

export default function VaultPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <VaultView data={data} />;
}
