"use client";

import useSWR from "swr";

import { AgentsView } from "@/components/dashboard/overview-views";
import { fetchDashboard } from "@/lib/authsome-api";

export default function AgentsPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <AgentsView data={data} />;
}
