"use client";

import useSWR from "swr";

import { ConnectionsView } from "@/components/authsome-dashboard";
import { fetchDashboard } from "@/lib/authsome-api";

export default function ConnectionsPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <ConnectionsView connections={data.connections} />;
}
