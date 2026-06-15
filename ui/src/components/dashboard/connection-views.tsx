"use client";

import { Globe2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import {
  INTERACTIVE_ROW_CLASS,
  SearchInput,
  StatusBadge,
  connectionDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { PageEmptyState } from "@/components/dashboard/page-state";
import { SectionHeader } from "@/components/dashboard/section-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DashboardData, GlobalConnectionRow, unsetGlobalConnection } from "@/lib/authsome-api";

export function ConnectionsView({
  connections,
  globalConnections,
  initialFilter,
  isAdmin,
  onRefresh,
}: {
  connections: DashboardData["connections"];
  globalConnections: DashboardData["globalConnections"];
  initialFilter?: string;
  isAdmin: boolean;
  onRefresh: () => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState(initialFilter ?? "");
  const filteredConnections = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return connections;
    return connections.filter((row) =>
      `${row.connectionName} ${row.providerDisplayName} ${row.authTypeLabel}`.toLowerCase().includes(normalized),
    );
  }, [connections, query]);
  const filteredGlobalConnections = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return globalConnections;
    return globalConnections.filter((row) =>
      `${row.connectionName} ${row.providerDisplayName} ${row.authTypeLabel} ${row.accountLabel || ""}`
        .toLowerCase()
        .includes(normalized),
    );
  }, [globalConnections, query]);

  return (
    <div className="grid gap-5">
      <SectionHeader description="Connection fallbacks and named connections in the current vault." title="Connections" />
      <SearchInput onChange={setQuery} placeholder="Search connections..." value={query} />
      <GlobalConnectionsSection connections={filteredGlobalConnections} isAdmin={isAdmin} onRefresh={onRefresh} />
      <Card className="shadow-none border-border/50">
        <CardHeader>
          <CardTitle>Your Connections</CardTitle>
          <CardDescription>Named connections in the current vault.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {filteredConnections.length ? (
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
                {filteredConnections.map((row) => {
                  const href = connectionDetailHref(row.providerName, row.connectionName);
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
                      <span className="font-medium">{row.connectionName}</span>
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
          ) : <PageEmptyState title="No connections found" />}
        </CardContent>
      </Card>
    </div>
  );
}

function GlobalConnectionsSection({
  connections,
  isAdmin,
  onRefresh,
}: {
  connections: GlobalConnectionRow[];
  isAdmin: boolean;
  onRefresh: () => void;
}) {
  const router = useRouter();

  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <CardTitle>Global Connections</CardTitle>
        <CardDescription>Deployment-wide fallback connections available to accepted agents.</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {connections.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Connection</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                {isAdmin ? <TableHead className="w-24">Actions</TableHead> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {connections.map((row) => {
                const href = connectionDetailHref(row.providerName, row.connectionName);
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
                    <div className="flex min-w-0 items-center gap-2">
                      <Globe2 className="size-4 shrink-0 text-muted-foreground" />
                      <div className="min-w-0">
                        <div className="truncate font-medium">{row.connectionName}</div>
                        {row.accountLabel ? (
                          <div className="truncate text-xs text-muted-foreground">{row.accountLabel}</div>
                        ) : null}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{row.providerDisplayName}</TableCell>
                  <TableCell className="text-muted-foreground">{row.authTypeLabel}</TableCell>
                  <TableCell>
                    <StatusBadge status={row.status} />
                  </TableCell>
                  {isAdmin ? (
                    <TableCell onClick={(event) => event.stopPropagation()}>
                      <RemoveGlobalConnectionButton onRefresh={onRefresh} provider={row.providerName} />
                    </TableCell>
                  ) : null}
                </TableRow>
                );
              })}
            </TableBody>
          </Table>
        ) : <PageEmptyState title="No global connections found" />}
      </CardContent>
    </Card>
  );
}

function RemoveGlobalConnectionButton({ onRefresh, provider }: { onRefresh: () => void; provider: string }) {
  const [working, setWorking] = useState(false);

  async function remove() {
    setWorking(true);
    try {
      await unsetGlobalConnection(provider);
      onRefresh();
    } finally {
      setWorking(false);
    }
  }

  return (
    <Button disabled={working} onClick={() => void remove()} size="sm" type="button" variant="outline">
      Remove
    </Button>
  );
}
