"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

import { ConnectionDetailBody } from "@/components/dashboard/connection-detail-view";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchConnectionDetail, fetchDashboard } from "@/lib/authsome-api";

function ConnectionDetailContent() {
  const searchParams = useSearchParams();
  const provider = searchParams.get("provider") ?? "";
  const connection = searchParams.get("connection") ?? "";
  const principal = searchParams.get("principal") ?? undefined;

  const { data, mutate } = useSWR(
    provider && connection ? ["authsome-connection-detail", provider, connection, principal] : null,
    () => fetchConnectionDetail(provider, connection, principal),
  );
  const { data: dashboard, mutate: mutateDashboard } = useSWR("authsome-dashboard", fetchDashboard);

  if (!provider || !connection) {
    return (
      <Card className="w-full max-w-md border-border/50 shadow-none">
        <CardHeader>
          <CardTitle>Connection not found</CardTitle>
          <CardDescription>Open a connection from the connections list to view its details.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link className={buttonVariants({ variant: "outline" })} href="/connections">
            Back to connections
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  return (
    <ConnectionDetailBody
      data={data}
      onRefresh={() => { void mutate(); void mutateDashboard(); }}
      principal={principal}
      providers={dashboard?.providers}
    />
  );
}

export default function ConnectionDetailPage() {
  return (
    <Suspense fallback={null}>
      <ConnectionDetailContent />
    </Suspense>
  );
}
