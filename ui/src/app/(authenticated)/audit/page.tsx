"use client";

import useSWR from "swr";

import { AuditView } from "@/components/dashboard/overview-views";
import { fetchDashboard } from "@/lib/authsome-api";

export default function AuditPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data || !data.account.isAdmin) return null;
  return <AuditView data={data} />;
}
