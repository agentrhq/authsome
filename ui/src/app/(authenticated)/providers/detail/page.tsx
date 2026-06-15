"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

import { ProviderDetailBody } from "@/components/dashboard/provider-detail-view";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchDashboard, fetchProviderDetail } from "@/lib/authsome-api";

function ProviderDetailContent() {
  const searchParams = useSearchParams();
  const provider = searchParams.get("provider") ?? "";
  const { data, mutate } = useSWR(
    provider ? ["authsome-provider-detail", provider] : null,
    () => fetchProviderDetail(provider),
  );
  const { mutate: mutateDashboard } = useSWR("authsome-dashboard", fetchDashboard);

  if (!provider) {
    return (
      <Card className="w-full max-w-md border-border/50 shadow-none">
        <CardHeader>
          <CardTitle>Provider not found</CardTitle>
          <CardDescription>Open a provider from the providers list to view its details.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link className={buttonVariants({ variant: "outline" })} href="/providers">
            Back to providers
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  return (
    <ProviderDetailBody
      data={data}
      onRefresh={() => { void mutate(); void mutateDashboard(); }}
    />
  );
}

export default function ProviderDetailPage() {
  return (
    <Suspense fallback={null}>
      <ProviderDetailContent />
    </Suspense>
  );
}
