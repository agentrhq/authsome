"use client";

import useSWR from "swr";

import { AboutSettingsContent } from "@/components/dashboard/settings-view";
import { fetchDashboard } from "@/lib/authsome-api";

export default function SettingsAboutPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return <AboutSettingsContent data={data} />;
}
