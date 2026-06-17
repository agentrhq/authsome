"use client";

import { Globe2, Link2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import {
  INTERACTIVE_ROW_CLASS,
  ProviderLogo,
  SearchInput,
  StatusBadge,
  connectionDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { PageEmptyState } from "@/components/dashboard/page-state";
import { SectionHeader } from "@/components/dashboard/section-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DashboardData, GlobalConnectionRow, ProviderView, unsetGlobalConnection } from "@/lib/authsome-api";

export function ConnectionsView({
  connections,
  globalConnections,
  initialFilter,
  isAdmin,
  onRefresh,
  providers,
}: {
  connections: DashboardData["connections"];
  globalConnections: DashboardData["globalConnections"];
  initialFilter?: string;
  isAdmin: boolean;
  onRefresh: () => void;
  providers?: ProviderView[];
}) {
  const router = useRouter();
  const [query, setQuery] = useState(initialFilter ?? "");
  const providerMap = useMemo(
    () => new Map((providers ?? []).map((p) => [p.name, p])),
    [providers],
  );
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

  const isFiltering = query.trim().length > 0;

  return (
    <div className="grid gap-5">
      <SectionHeader description="Named connections and deployment-wide fallbacks in the current vault." title="Connections" />
      <SearchInput onChange={setQuery} placeholder="Search connections..." value={query} />

      <Card className="shadow-none border-border/50">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Link2 className="size-4 text-muted-foreground" />
                Your Connections
              </CardTitle>
              <CardDescription>Named connections in the current vault.</CardDescription>
            </div>
            {isFiltering ? (
              <Badge variant="outline">
                {filteredConnections.length} of {connections.length}
              </Badge>
            ) : connections.length ? (
              <Badge variant="outline">{connections.length}</Badge>
            ) : null}
          </div>
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
              {isFiltering ? (
                <PageEmptyState title="No matching connections" />
              ) : (
                <PageEmptyState
                  actionLabel="Browse providers"
                  description="Connect a provider to create your first connection."
                  href="/providers"
                  title="No connections yet"
                />
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <GlobalConnectionsSection
        connections={filteredGlobalConnections}
        isAdmin={isAdmin}
        isFiltering={isFiltering}
        onRefresh={onRefresh}
        providerMap={providerMap}
        totalCount={globalConnections.length}
      />
    </div>
  );
}

function GlobalConnectionsSection({
  connections,
  isAdmin,
  isFiltering,
  onRefresh,
  providerMap,
  totalCount,
}: {
  connections: GlobalConnectionRow[];
  isAdmin: boolean;
  isFiltering: boolean;
  onRefresh: () => void;
  providerMap: Map<string, ProviderView>;
  totalCount: number;
}) {
  const router = useRouter();

  return (
    <Card className="shadow-none border-border/50 border-l-primary/40 border-l-2">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Globe2 className="size-4 text-primary/70" />
              Global Connections
            </CardTitle>
            <CardDescription>Deployment-wide fallback connections available to accepted agents.</CardDescription>
          </div>
          {isFiltering ? (
            <Badge variant="outline">
              {connections.length} of {totalCount}
            </Badge>
          ) : totalCount ? (
            <Badge variant="outline">{totalCount}</Badge>
          ) : null}
        </div>
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
                      <RemoveGlobalConnectionButton
                        connectionName={row.connectionName}
                        onRefresh={onRefresh}
                        provider={row.providerName}
                        providerDisplayName={row.providerDisplayName}
                      />
                    </TableCell>
                  ) : null}
                </TableRow>
                );
              })}
            </TableBody>
          </Table>
        ) : (
          <div className="p-4">
            {isFiltering ? (
              <PageEmptyState title="No matching global connections" />
            ) : (
              <PageEmptyState
                description="Admins can promote a connection to global from its detail page."
                title="No global connections"
              />
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RemoveGlobalConnectionButton({
  connectionName,
  onRefresh,
  provider,
  providerDisplayName,
}: {
  connectionName: string;
  onRefresh: () => void;
  provider: string;
  providerDisplayName: string;
}) {
  const [open, setOpen] = useState(false);
  const [working, setWorking] = useState(false);

  async function remove() {
    setWorking(true);
    try {
      await unsetGlobalConnection(provider);
      setOpen(false);
      onRefresh();
    } finally {
      setWorking(false);
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)} size="sm" type="button" variant="outline">
        Remove
      </Button>
      <Dialog onOpenChange={setOpen} open={open}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove global connection</DialogTitle>
            <DialogDescription>
              This will remove the global fallback for {providerDisplayName} ({connectionName}).
              Agents without their own connection will no longer have access.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setOpen(false)} type="button" variant="outline">
              Cancel
            </Button>
            <Button disabled={working} onClick={() => void remove()} type="button" variant="destructive">
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
