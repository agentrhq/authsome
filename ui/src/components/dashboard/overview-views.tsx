"use client";

import { UserRound } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import useSWR from "swr";

import { PageEmptyState, PageErrorState, PageLoadingState } from "@/components/dashboard/page-state";
import { ProviderSummary } from "@/components/dashboard/provider-views";
import { SectionHeader } from "@/components/dashboard/section-header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DashboardData, PrincipalRow, fetchAuditEvents, fetchPrincipals } from "@/lib/authsome-api";

export function DashboardView({ data }: { data: DashboardData }) {
  const recentEvents = data.audit.events.slice(0, 5);

  return (
    <div className="grid gap-8">
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold">Connected Apps</h2>
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

      <section>
        <div className="mb-4">
          <h2 className="text-base font-semibold">Agents</h2>
        </div>
        {data.identities.length ? (
          <div className="grid gap-2">
            {data.identities.map((identity) => (
              <div
                className="flex items-center justify-between rounded-lg border bg-muted/30 px-4 py-3"
                key={identity.handle}
              >
                <div className="flex items-center gap-3">
                  <UserRound className="size-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{identity.handle}</span>
                </div>
                {identity.isActive ? <Badge variant="outline">Active</Badge> : null}
              </div>
            ))}
          </div>
        ) : (
          <PageEmptyState title="No identities found" />
        )}
      </section>

      {data.audit.canView && recentEvents.length > 0 ? (
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Recent Events</h2>
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
                      <TableCell className="text-sm font-medium">{event.event}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{event.target}</TableCell>
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

export function AgentsView({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Local Ed25519 key pairs (agents) claimed to this account." title="Agents" />
      <Card className="shadow-none border-border/50">
        <CardContent className="p-0">
          {data.identities.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.identities.map((identity) => (
                  <TableRow key={identity.handle}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-muted">
                          <UserRound className="size-3.5 text-muted-foreground" />
                        </span>
                        <span className="font-medium">{identity.handle}</span>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : <PageEmptyState title="No agents found" />}
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
                      <span className="font-mono text-xs text-muted-foreground">{principal.principal_id}</span>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={principal.role === "admin" ? "border-amber-800 bg-amber-950/50 text-amber-400" : ""}
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
      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}
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
                        <Badge className="border-emerald-800 bg-emerald-950/50 text-emerald-400" variant="outline">
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
