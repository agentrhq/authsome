"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";

import { AgentDetailBody } from "@/components/dashboard/agent-detail-view";
import { PageErrorState, PageLoadingState } from "@/components/dashboard/page-state";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, fetchAgentDetail, fetchAuditEvents } from "@/lib/authsome-api";

function AgentNotFoundCard() {
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

function AgentDetailContent() {
  const searchParams = useSearchParams();
  const agent = searchParams.get("agent") ?? "";
  const detail = useSWR(agent ? ["authsome-agent-detail", agent] : null, () => fetchAgentDetail(agent));
  const audit = useSWR(agent ? ["authsome-agent-audit", agent] : null, () => fetchAuditEvents({ identity: agent, limit: 25 }));

  if (!agent) {
    return <AgentNotFoundCard />;
  }

  if (detail.error instanceof ApiError && detail.error.status === 404) {
    return <AgentNotFoundCard />;
  }

  if (detail.error || audit.error) {
    return <PageErrorState title="Failed to load agent details" />;
  }

  if (!detail.data || !audit.data) {
    return (
      <Card className="shadow-none border-border/50">
        <CardContent className="p-0">
          <PageLoadingState columns={4} />
        </CardContent>
      </Card>
    );
  }

  return <AgentDetailBody agent={detail.data} events={audit.data.events} />;
}

export default function AgentDetailPage() {
  return (
    <Suspense fallback={null}>
      <AgentDetailContent />
    </Suspense>
  );
}
