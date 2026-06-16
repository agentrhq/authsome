"use client";

import useSWR from "swr";

import { GeneralSettingsContent } from "@/components/dashboard/settings-view";
import { fetchDashboard } from "@/lib/authsome-api";

export default function SettingsGeneralPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <GeneralSettingsContent data={data} />;
}
