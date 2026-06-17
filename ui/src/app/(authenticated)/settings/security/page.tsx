"use client";

import { Suspense } from "react";
import useSWR from "swr";

import { SecuritySettingsContent } from "@/components/dashboard/settings-view";
import { fetchDashboard } from "@/lib/authsome-api";

export default function SettingsSecurityPage() {
  const { data } = useSWR("authsome-dashboard", fetchDashboard);
  if (!data) return null;
  return (
    <Suspense>
      <SecuritySettingsContent data={data} />
    </Suspense>
  );
}
