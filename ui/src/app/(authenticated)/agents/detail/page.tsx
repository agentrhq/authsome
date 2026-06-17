"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

import { AgentDetailBody } from "@/components/dashboard/agent-detail-view";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchDashboard } from "@/lib/authsome-api";

function AgentDetailContent() {
  const searchParams = useSearchParams();
  const handle = searchParams.get("agent") ?? "";

  const { data } = useSWR("authsome-dashboard", fetchDashboard);

  if (!handle) {
    return (
      <Card className="w-full max-w-md border-border/50 shadow-none">
        <CardHeader>
          <CardTitle>Agent not found</CardTitle>
          <CardDescription>Open an agent from the agents list to view its details.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link className={buttonVariants({ variant: "outline" })} href="/agents">
            Back to agents
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const agent = data.agents.find((a) => a.handle === handle);
  if (!agent) {
    return (
      <Card className="w-full max-w-md border-border/50 shadow-none">
        <CardHeader>
          <CardTitle>Agent not found</CardTitle>
          <CardDescription>The agent &ldquo;{handle}&rdquo; was not found in this account.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link className={buttonVariants({ variant: "outline" })} href="/agents">
            Back to agents
          </Link>
        </CardContent>
      </Card>
    );
  }

  return <AgentDetailBody agent={agent} data={data} />;
}

export default function AgentDetailPage() {
  return (
    <Suspense fallback={null}>
      <AgentDetailContent />
    </Suspense>
  );
}
