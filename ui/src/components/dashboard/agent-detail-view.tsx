"use client";

import { ArrowLeft, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { PageEmptyState } from "@/components/dashboard/page-state";
import { SectionHeader } from "@/components/dashboard/section-header";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AgentDetail, AuditRow } from "@/lib/authsome-api";
import { cn } from "@/lib/utils";

export function AgentDetailBody({
  agent,
  events,
}: {
  agent: AgentDetail;
  events: AuditRow[];
}) {
  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeader
          description="Cryptographic signing identity claimed to this account."
          title={agent.handle}
        />
        <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/agents">
          <ArrowLeft />
          Agents
        </Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UserRound className="size-4 text-muted-foreground" />
              Identity
            </CardTitle>
            <CardDescription>Local Ed25519 agent metadata and claim state.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <DetailRow label="Handle" value={agent.handle} />
            <DetailRow code label="DID" value={agent.did} />
            <DetailRow label="Created" value={formatDate(agent.created_at)} />
            <DetailRow label="Claimed" value={formatDate(agent.claimed_at)} />
          </CardContent>
        </Card>

        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-4 text-muted-foreground" />
              Owner
            </CardTitle>
            <CardDescription>Principal ownership for this signing identity.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <DetailRow label="Claim Status" value={<StatusBadge status={agent.claim_status ?? agent.registration_status} />} />
            <DetailRow label="Active Agent" value={agent.is_active ? "Yes" : "No"} />
            <DetailRow label="Principal" value={agent.principal_email || agent.principal_id || "-"} />
            <DetailRow code label="Principal ID" value={agent.principal_id || "-"} />
          </CardContent>
        </Card>
      </div>

      <Card className="shadow-none border-border/50">
        <CardHeader>
          <CardTitle className="text-base">Recent Activity</CardTitle>
          <CardDescription>Recent audit events recorded for this agent.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {events.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow key={event.eventId}>
                    <TableCell className="whitespace-nowrap font-mono text-xs text-muted-foreground">
                      {event.time}
                    </TableCell>
                    <TableCell className="font-medium">{event.event}</TableCell>
                    <TableCell className="text-muted-foreground">{event.target}</TableCell>
                    <TableCell>{event.status && event.status !== "-" ? <StatusBadge status={event.status} /> : null}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-4">
              <PageEmptyState title="No audit events found" />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DetailRow({
  code = false,
  label,
  value,
}: {
  code?: boolean;
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[120px_minmax(0,1fr)] sm:items-start">
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      {code ? (
        <code className="-ml-2 min-w-0 break-all rounded bg-muted py-1 pl-2 pr-2 font-mono text-sm font-medium leading-5">
          {value}
        </code>
      ) : (
        <div className="min-w-0 text-sm font-medium">{value}</div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  return (
    <Badge
      className={cn(
        normalized === "accepted" || normalized === "claimed" || normalized === "success"
          ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400"
          : "",
        normalized === "rejected" || normalized === "failure" || normalized === "error"
          ? "border-destructive/60 bg-destructive/10 text-destructive"
          : "",
      )}
      variant="outline"
    >
      {status}
    </Badge>
  );
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return parsed.toISOString().replace("T", " ").slice(0, 16) + " UTC";
}
