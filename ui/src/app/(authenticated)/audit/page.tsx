"use client";

import useSWR from "swr";

import { AuditView } from "@/components/authsome-dashboard";
import { fetchDashboard } from "@/lib/authsome-api";

export default function AuditPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <AuditView data={data} />;
}
