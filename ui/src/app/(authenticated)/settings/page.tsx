"use client";

import useSWR from "swr";

import { SettingsView } from "@/components/authsome-dashboard";
import { fetchDashboard } from "@/lib/authsome-api";

export default function SettingsPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <SettingsView data={data} />;
}
