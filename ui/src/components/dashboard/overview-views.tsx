"use client";

import { UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import useSWR from "swr";

import {
  INTERACTIVE_ROW_CLASS,
  SearchInput,
  agentDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { PageEmptyState, PageErrorState, PageLoadingState } from "@/components/dashboard/page-state";
import { ProviderSummary } from "@/components/dashboard/provider-views";
import { SectionHeader } from "@/components/dashboard/section-header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { H4 } from "@/components/ui/typography";
import { DashboardData, PrincipalRow, fetchAuditEvents, fetchPrincipals } from "@/lib/authsome-api";

export function DashboardView({ data }: { data: DashboardData }) {
  const recentEvents = data.audit.events.slice(0, 5);

  return (
    <div className="grid gap-5">
      <section aria-labelledby="connected-apps-heading">
        <div className="mb-3 flex items-center justify-between">
          <H4 id="connected-apps-heading">Connected Apps</H4>
          <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/providers">
            Browse
          </Link>
        </div>
        {data.connectedProviders.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.connectedProviders.map((provider) => (
              <ProviderSummary key={provider.name} provider={provider} />
            ))}
          </div>
        ) : (
          <PageEmptyState
            actionLabel="Browse providers"
            href="/providers"
            title="No connections yet"
          />
        )}
      </section>

      <section aria-labelledby="agents-heading">
        <div className="mb-3 flex items-center justify-between">
          <H4 id="agents-heading">Agents</H4>
          <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/agents">
            View all
          </Link>
        </div>
        {data.agents.length ? (
          <div className="grid gap-1.5">
            {data.agents.map((agent) => (
              <Link
                className="flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2.5 transition-colors hover:border-primary/60 hover:bg-primary/[0.03]"
                href={agentDetailHref(agent.handle)}
                key={agent.handle}
              >
                <div className="flex items-center gap-2.5">
                  <UserRound className="size-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{agent.handle}</span>
                </div>
                <div className="flex items-center gap-2">
                  <AgentClaimBadge status={agent.claimStatus} />
                  {agent.isActive ? (
                    <Badge className="border-primary/30 bg-primary/10 text-primary" variant="outline">
                      Active
                    </Badge>
                  ) : null}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <PageEmptyState
            description="Run 'authsome onboard' from an agent to register it."
            title="No agents found"
          />
        )}
      </section>

      {data.audit.canView && recentEvents.length > 0 ? (
        <section aria-labelledby="recent-events-heading">
          <div className="mb-3 flex items-center justify-between">
            <H4 id="recent-events-heading">Recent Events</H4>
            <Link className={buttonVariants({ size: "sm", variant: "outline" })} href="/audit">
              View all
            </Link>
          </div>
          <Card className="shadow-none border-border/50">
            <CardContent className="p-0">
              <Table>
                <TableBody>
                  {recentEvents.map((event) => (
                    <TableRow key={event.eventId}>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {event.time}
                      </TableCell>
                      <TableCell className="font-medium">{event.event}</TableCell>
                      <TableCell className="text-muted-foreground">{event.target}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </section>
      ) : null}
    </div>
  );
}

function AgentClaimBadge({ status }: { status: string }) {
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

export function AgentsView({ data }: { data: DashboardData }) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const filteredAgents = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return data.agents;
    return data.agents.filter((agent) =>
      `${agent.handle} ${agent.claimStatus}`.toLowerCase().includes(normalized),
    );
  }, [data.agents, query]);

  const isFiltering = query.trim().length > 0;

  return (
    <div className="grid gap-5">
      <SectionHeader description="Local Ed25519 key pairs (agents) claimed to this account." title="Agents" />
      {data.agents.length > 1 ? (
        <SearchInput onChange={setQuery} placeholder="Search agents..." value={query} />
      ) : null}

      <Card className="shadow-none border-border/50">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <UserRound className="size-4 text-muted-foreground" />
                Claimed Agents
              </CardTitle>
              <CardDescription>Agents with accepted identity claims in this account.</CardDescription>
            </div>
            {isFiltering ? (
              <Badge variant="outline">
                {filteredAgents.length} of {data.agents.length}
              </Badge>
            ) : data.agents.length ? (
              <Badge variant="outline">{data.agents.length}</Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {filteredAgents.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead>Claim</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAgents.map((agent) => {
                  const href = agentDetailHref(agent.handle);
                  return (
                    <TableRow
                      className={INTERACTIVE_ROW_CLASS}
                      key={agent.handle}
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
                          <span className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-border/60 bg-muted">
                            <UserRound className="size-3.5 text-muted-foreground" />
                          </span>
                          <span className="truncate font-medium">{agent.handle}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <AgentClaimBadge status={agent.claimStatus} />
                      </TableCell>
                      <TableCell>
                        {agent.isActive ? (
                          <Badge className="border-primary/30 bg-primary/10 text-primary" variant="outline">
                            Active
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="p-4">
              {isFiltering ? (
                <PageEmptyState title="No matching agents" />
              ) : (
                <PageEmptyState
                  description="Run 'authsome onboard' from an agent to register it."
                  title="No agents found"
                />
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function PrincipalsView() {
  const { data, error } = useSWR<PrincipalRow[]>("authsome-principals", fetchPrincipals);

  return (
    <div className="grid gap-5">
      <SectionHeader description="All registered principals and their account roles." title="Principals" />
      <Card className="shadow-none border-border/50">
        <CardContent className="p-0">
          {error ? (
            <PageErrorState title="Failed to load principals" />
          ) : !data ? (
            <PageLoadingState columns={4} />
          ) : data.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Principal ID</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((principal) => (
                  <TableRow key={principal.principal_id}>
                    <TableCell className="font-medium">{principal.email || "-"}</TableCell>
                    <TableCell>
                      <code className="font-mono text-xs text-muted-foreground">{principal.principal_id}</code>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={principal.role === "admin" ? "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-400" : ""}
                        variant="outline"
                      >
                        {principal.role}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {principal.created_at ? new Date(principal.created_at).toISOString().slice(0, 10) : "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : <PageEmptyState title="No principals found" />}
        </CardContent>
      </Card>
    </div>
  );
}

export function AuditView({ data }: { data: DashboardData }) {
  const [auditResult, setAuditResult] = useState<{
    events: DashboardData["audit"]["events"];
    nextCursor: string | null;
  } | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const requestSequence = useRef(0);
  const events = auditResult?.events ?? data.audit.events;
  const nextCursor = auditResult?.nextCursor ?? data.audit.nextCursor;
  const description = data.account.isAdmin
    ? "Recent administrative and credential events."
    : "Recent account, identity, vault, and credential events for this principal.";

  function nextRequestId(): number {
    requestSequence.current += 1;
    return requestSequence.current;
  }

  function isLatestRequest(requestId: number): boolean {
    return requestSequence.current === requestId;
  }

  async function loadMore() {
    if (!nextCursor) return;
    const requestId = nextRequestId();
    setLoadingMore(true);
    setErrorMessage("");
    try {
      const result = await fetchAuditEvents({ cursor: nextCursor, limit: 50 });
      if (!isLatestRequest(requestId)) return;
      setAuditResult({
        events: [...events, ...result.events],
        nextCursor: result.nextCursor,
      });
    } catch (error) {
      if (!isLatestRequest(requestId)) return;
      setErrorMessage(error instanceof Error ? error.message : "Failed to load more audit events.");
    } finally {
      if (isLatestRequest(requestId)) {
        setLoadingMore(false);
      }
    }
  }

  return (
    <div className="grid gap-5">
      <SectionHeader description={description} title="Audit Log" />
      {errorMessage ? (
        <p className="text-sm text-destructive" role="alert">{errorMessage}</p>
      ) : null}
      <Card className="shadow-none border-border/50">
        <CardContent className="p-0">
          {events.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow key={event.eventId}>
                    <TableCell className="whitespace-nowrap font-mono text-xs text-muted-foreground">{event.time}</TableCell>
                    <TableCell className="font-medium">{event.event}</TableCell>
                    <TableCell className="text-muted-foreground">{event.actor}</TableCell>
                    <TableCell className="text-muted-foreground">{event.target}</TableCell>
                    <TableCell>
                      {event.status === "success" ? (
                        <Badge className="border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400" variant="outline">
                          {event.status}
                        </Badge>
                      ) : event.status === "failure" || event.status === "error" ? (
                        <Badge className="border-destructive/60 bg-destructive/10 text-destructive" variant="outline">
                          {event.status}
                        </Badge>
                      ) : event.status ? (
                        <Badge variant="outline">{event.status}</Badge>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : <PageEmptyState title="No audit events found" />}
        </CardContent>
      </Card>
      {nextCursor ? (
        <div className="flex justify-center">
          <Button disabled={loadingMore} onClick={() => void loadMore()} type="button" variant="outline">
            {loadingMore ? "Loading..." : "Load more"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
