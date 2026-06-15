"use client";

import useSWR from "swr";

import { DashboardView } from "@/components/dashboard/overview-views";
import { fetchDashboard } from "@/lib/authsome-api";

export default function DashboardPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <DashboardView data={data} />;
}
