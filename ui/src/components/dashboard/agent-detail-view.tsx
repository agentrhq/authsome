"use client";

import { KeyRound, Link2, Mail, Shield, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  INTERACTIVE_ROW_CLASS,
  ProviderLogo,
  StatusBadge,
  connectionDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { agentDetailHref } from "@/components/dashboard/overview-views";
import { PageEmptyState } from "@/components/dashboard/page-state";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { H3 } from "@/components/ui/typography";
import { AgentRow, DashboardData } from "@/lib/authsome-api";

function DetailField({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="grid gap-1">
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div>{children}</div>
    </div>
  );
}

function ClaimStatusBadge({ status }: { status: string }) {
  if (status === "accepted") {
    return (
      <Badge className="border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400" variant="outline">
        Accepted
      </Badge>
    );
  }
  if (status === "pending") {
    return (
      <Badge className="border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-400" variant="outline">
        Pending
      </Badge>
    );
  }
  if (status === "rejected") {
    return (
      <Badge className="border-destructive/60 bg-destructive/10 text-destructive" variant="outline">
        Rejected
      </Badge>
    );
  }
  return <Badge variant="outline">{status}</Badge>;
}

export function AgentDetailBody({
  agent,
  data,
}: {
  agent: AgentRow;
  data: DashboardData;
}) {
  const router = useRouter();
  const providerMap = new Map(data.providers.map((p) => [p.name, p]));
  const agentConnections = data.connections.filter(() => agent.isActive);

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/50 pb-4">
        <div className="flex items-center gap-3 min-w-0">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border/60 bg-muted">
            <UserRound className="size-5 text-muted-foreground" />
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Link className="text-sm text-muted-foreground hover:text-foreground hover:underline" href="/agents">
                Agents
              </Link>
            </div>
            <H3 className="mt-0.5 leading-tight">{agent.handle}</H3>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ClaimStatusBadge status={agent.claimStatus} />
          {agent.isActive ? (
            <Badge className="border-primary/30 bg-primary/10 text-primary" variant="outline">
              Active
            </Badge>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-border/50 shadow-none">
          <CardHeader className="pb-0">
            <CardTitle className="flex items-center gap-2">
              <Shield className="size-4 text-muted-foreground" />
              Identity
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 pt-4">
            <DetailField label="Handle">
              <span className="text-sm font-medium">{agent.handle}</span>
            </DetailField>
            <DetailField label="Claim Status">
              <ClaimStatusBadge status={agent.claimStatus} />
            </DetailField>
            <DetailField label="Session">
              <span className="text-sm">{agent.isActive ? "Active (current session)" : "Inactive"}</span>
            </DetailField>
          </CardContent>
        </Card>

        <Card className="border-border/50 shadow-none">
          <CardHeader className="pb-0">
            <CardTitle className="flex items-center gap-2">
              <Mail className="size-4 text-muted-foreground" />
              Owner
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 pt-4">
            <DetailField label="Account">
              <span className="text-sm">{data.account.email || "-"}</span>
            </DetailField>
            <DetailField label="Role">
              {data.account.roleLabel ? (
                <Badge
                  className={data.account.roleLabel === "Admin" ? "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-400" : ""}
                  variant="outline"
                >
                  {data.account.roleLabel}
                </Badge>
              ) : (
                <span className="text-sm">-</span>
              )}
            </DetailField>
            <DetailField label="Principal ID">
              <code className="text-xs font-mono text-muted-foreground">{data.account.principalId || "-"}</code>
            </DetailField>
          </CardContent>
        </Card>
      </div>

      {agent.isActive ? (
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Link2 className="size-4 text-muted-foreground" />
                  Connections
                </CardTitle>
                <CardDescription>Connections available to this agent in the current vault.</CardDescription>
              </div>
              {agentConnections.length ? (
                <Badge variant="outline">{agentConnections.length}</Badge>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {agentConnections.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Connection</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agentConnections.map((row) => {
                    const href = connectionDetailHref(row.providerName, row.connectionName);
                    const provider = providerMap.get(row.providerName);
                    return (
                      <TableRow
                        className={INTERACTIVE_ROW_CLASS}
                        key={`${row.providerName}:${row.connectionName}`}
                        onClick={() => router.push(href)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            router.push(href);
                          }
                        }}
                        role="link"
                        tabIndex={0}
                      >
                        <TableCell>
                          <div className="flex min-w-0 items-center gap-2.5">
                            {provider ? (
                              <ProviderLogo className="size-7 shrink-0" initial={provider.logoInitial} logo={provider.logo} />
                            ) : null}
                            <span className="truncate font-medium">{row.connectionName}</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{row.providerDisplayName}</TableCell>
                        <TableCell className="text-muted-foreground">{row.authTypeLabel}</TableCell>
                        <TableCell>
                          <StatusBadge status={row.status} />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            ) : (
              <div className="p-4">
                <PageEmptyState
                  actionLabel="Browse providers"
                  description="Connect a provider to create a connection for this agent."
                  href="/providers"
                  title="No connections yet"
                />
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
