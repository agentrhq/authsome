"use client";

import {
  AppWindow,
  CheckCircle2,
  CircleAlert,
  ClipboardList,
  Database,
  ExternalLink,
  GitBranch,
  KeyRound,
  LayoutDashboard,
  Link2,
  LogIn,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { FormEvent, ReactNode, useMemo, useState } from "react";
import useSWR from "swr";

import { ApiError, DashboardData, ProviderView, fetchDashboard } from "@/lib/authsome-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type View = "dashboard" | "providers" | "connections" | "vault" | "audit" | "settings";

type NavItem = {
  id: View;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard /> },
  { id: "providers", label: "Providers", icon: <AppWindow /> },
  { id: "connections", label: "Connections", icon: <Link2 /> },
  { id: "vault", label: "Vault", icon: <Database /> },
  { id: "audit", label: "Audit Log", icon: <ClipboardList />, adminOnly: true },
  { id: "settings", label: "Settings", icon: <Settings /> },
];

const NEXT_URL = "/";

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "connected") {
    return (
      <Badge className="border-emerald-800 bg-emerald-950/50 text-emerald-400" variant="outline">
        <CheckCircle2 />
        Connected
      </Badge>
    );
  }
  if (status === "reauth" || status === "expired" || status === "error") {
    return (
      <Badge className="border-amber-800 bg-amber-950/50 text-amber-400" variant="outline">
        <CircleAlert />
        Re-auth
      </Badge>
    );
  }
  return <Badge variant="secondary">Available</Badge>;
}

function AuthGate() {
  return (
    <main className="min-h-screen bg-background px-6 py-10 flex items-center">
      <section className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="flex flex-col justify-between rounded-lg border bg-card p-8">
          <div>
            <div className="mb-5 inline-flex size-11 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="size-5" />
            </div>
            <h1 className="text-3xl font-semibold leading-tight text-foreground">Authsome</h1>
            <p className="mt-3 max-w-sm text-sm leading-6 text-muted-foreground">
              Local credential access for identities, vaults, providers, and audit history.
            </p>
          </div>
          <div className="mt-10 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg border bg-muted p-3">
              <div className="font-medium">Local daemon</div>
              <div className="mt-1 text-muted-foreground">127.0.0.1:7998</div>
            </div>
            <div className="rounded-lg border bg-muted p-3">
              <div className="font-medium">Browser session</div>
              <div className="mt-1 text-muted-foreground">HttpOnly cookie</div>
            </div>
          </div>
        </div>
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle>Open Dashboard</CardTitle>
            <CardDescription>Use your Authsome account to continue.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 md:grid-cols-2">
            <AccountForm action="/auth/login" title="Sign in" submitLabel="Sign in" />
            <AccountForm action="/auth/register" title="Create account" submitLabel="Create account" />
          </CardContent>
        </Card>
      </section>
    </main>
  );
}

function AccountForm({
  action,
  title,
  submitLabel,
}: {
  action: string;
  title: string;
  submitLabel: string;
}) {
  return (
    <form action={action} className="grid gap-3 rounded-lg border bg-background p-4" method="post">
      <input name="next" type="hidden" value={NEXT_URL} />
      <div className="text-sm font-semibold">{title}</div>
      <label className="grid gap-1.5 text-sm">
        <span className="text-muted-foreground">Email</span>
        <Input autoComplete="email" name="email" required type="email" />
      </label>
      <label className="grid gap-1.5 text-sm">
        <span className="text-muted-foreground">Password</span>
        <Input autoComplete="current-password" minLength={8} name="password" required type="password" />
      </label>
      <Button className="mt-1" type="submit">
        <LogIn />
        {submitLabel}
      </Button>
    </form>
  );
}

function LoadingScreen() {
  return (
    <main className="grid min-h-screen grid-cols-1 bg-background md:grid-cols-[240px_1fr]">
      <aside className="hidden border-r bg-card p-5 md:block">
        <Skeleton className="h-9 w-32" />
        <div className="mt-8 grid gap-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton className="h-8 w-full" key={index} />
          ))}
        </div>
      </aside>
      <section className="p-6">
        <Skeleton className="h-10 w-56" />
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton className="h-32 rounded-lg" key={index} />
          ))}
        </div>
      </section>
    </main>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="max-w-md shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CircleAlert className="size-5 text-destructive" />
            Dashboard Unavailable
          </CardTitle>
          <CardDescription>The daemon did not return dashboard data.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={onRetry} type="button">
            <RefreshCw />
            Retry
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}

function Sidebar({
  activeView,
  data,
  onChange,
}: {
  activeView: View;
  data: DashboardData;
  onChange: (view: View) => void;
}) {
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || data.account.isAdmin);

  return (
    <aside className="flex border-r bg-sidebar md:min-h-screen md:w-64 md:flex-col">
      <div className="hidden border-b px-5 py-5 md:block">
        <div className="flex items-center gap-3">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheck className="size-4" />
          </div>
          <div>
            <div className="text-sm font-semibold">Authsome</div>
            <div className="text-xs text-muted-foreground">v{data.version}</div>
          </div>
        </div>
      </div>
      <ScrollArea className="w-full md:flex-1">
        <nav className="flex gap-1 overflow-x-auto p-3 md:grid md:gap-1 md:overflow-visible">
          {items.map((item) => (
            <button
              className={cn(
                "inline-flex h-9 shrink-0 items-center gap-2 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:w-full",
                activeView === item.id && "bg-sidebar-accent text-sidebar-accent-foreground",
              )}
              key={item.id}
              onClick={() => onChange(item.id)}
              type="button"
            >
              <span className="[&_svg]:size-4">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </ScrollArea>
      <div className="hidden border-t p-4 md:block">
        <div className="rounded-lg border bg-muted p-3">
          <div className="text-xs font-medium uppercase text-muted-foreground">Signed in</div>
          <div className="mt-1 truncate text-sm font-medium">{data.account.email || data.account.identity}</div>
          {data.account.roleLabel ? (
            <Badge className="mt-2" variant="outline">
              {data.account.roleLabel}
            </Badge>
          ) : null}
        </div>
      </div>
    </aside>
  );
}

function Topbar() {
  return (
    <header className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b bg-card px-4 py-3 md:px-6">
      <div>
        <div className="text-xs font-medium uppercase text-muted-foreground">Local Dashboard</div>
        <div className="text-lg font-semibold leading-tight">Workspace Status</div>
      </div>
      <div className="flex items-center gap-2">
        <Button render={<a href="https://authsome.mbajaj.me" rel="noreferrer" target="_blank" />} size="sm" variant="outline">
          <ExternalLink />
          Docs
        </Button>
        <Button render={<a href="https://github.com/agentrhq/authsome" rel="noreferrer" target="_blank" />} size="sm" variant="outline">
          <GitBranch />
          GitHub
        </Button>
        <form action="/logout" method="post">
          <input name="return_url" type="hidden" value={NEXT_URL} />
          <Button size="sm" type="submit" variant="secondary">
            <LogOut />
            Sign out
          </Button>
        </form>
      </div>
    </header>
  );
}

function StatCards({ data }: { data: DashboardData }) {
  const stats = [
    { label: "Connected Apps", value: data.stats.connected, foot: `${data.stats.available} available`, icon: <AppWindow /> },
    { label: "Next Expiry", value: data.lastActivity, foot: "Across active providers", icon: <KeyRound /> },
    { label: "Auth Types", value: `${data.stats.oauth} / ${data.stats.apiKey}`, foot: "OAuth 2.0 / API Key", icon: <ShieldCheck /> },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {stats.map((stat) => (
        <Card className="shadow-none border-border/60" key={stat.label}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardDescription>{stat.label}</CardDescription>
            <span className="text-muted-foreground [&_svg]:size-4">{stat.icon}</span>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold text-foreground">{stat.value}</div>
            <p className="mt-1 text-sm text-muted-foreground">{stat.foot}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function DashboardView({ data, onViewChange }: { data: DashboardData; onViewChange: (view: View) => void }) {
  return (
    <div className="grid gap-6">
      <StatCards data={data} />
      <section className="grid gap-4 lg:grid-cols-[1.4fr_0.8fr]">
        <Card className="shadow-none border-border/50">
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle>Connected Providers</CardTitle>
              <CardDescription>Active credential surfaces in the current vault.</CardDescription>
            </div>
            <Button onClick={() => onViewChange("connections")} size="sm" type="button" variant="outline">
              Manage
            </Button>
          </CardHeader>
          <CardContent>
            {data.connectedProviders.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                {data.connectedProviders.slice(0, 6).map((provider) => (
                  <ProviderSummary provider={provider} key={provider.name} />
                ))}
              </div>
            ) : (
              <EmptyBlock actionLabel="Browse providers" onAction={() => onViewChange("providers")} title="No connections yet" />
            )}
          </CardContent>
        </Card>
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle>Vault</CardTitle>
            <CardDescription>Default credential namespace.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <KeyValue label="Handle" value={data.vault.handle} />
            <AdvancedSection>
              <KeyValue label="Vault ID" value={data.vault.vaultId || "-"} />
              <KeyValue label="Principal" value={data.account.principalId || "-"} />
            </AdvancedSection>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function ProviderSummary({ provider }: { provider: ProviderView }) {
  return (
    <div className="rounded-lg border border-border/50 bg-muted/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-lg bg-muted font-semibold text-primary">
            {provider.logoInitial}
          </span>
          <div>
            <div className="font-medium">{provider.displayName}</div>
            <div className="text-sm text-muted-foreground">{provider.authTypeLabel}</div>
          </div>
        </div>
        <StatusBadge status={provider.status} />
      </div>
      <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{provider.description || provider.apiUrl}</p>
    </div>
  );
}

function EmptyBlock({ actionLabel, onAction, title }: { actionLabel: string; onAction: () => void; title: string }) {
  return (
    <div className="rounded-lg border border-dashed bg-muted/50 p-6 text-center">
      <div className="font-medium">{title}</div>
      <Button className="mt-4" onClick={onAction} size="sm" type="button">
        <Plus />
        {actionLabel}
      </Button>
    </div>
  );
}

function ProvidersView({ providers }: { providers: ProviderView[] }) {
  const [query, setQuery] = useState("");
  const [dialogProvider, setDialogProvider] = useState<ProviderView | null>(null);

  const filteredProviders = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return providers;
    }
    return providers.filter((provider) =>
      `${provider.displayName} ${provider.name} ${provider.authTypeLabel}`.toLowerCase().includes(normalized),
    );
  }, [providers, query]);

  return (
    <div className="grid gap-5">
      <SectionHeader description="Configure providers and start browser login flows." title="Providers" />
      <SearchInput onChange={setQuery} placeholder="Search providers..." value={query} />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filteredProviders.map((provider) => (
          <ProviderCard key={provider.name} onNamedLogin={() => setDialogProvider(provider)} provider={provider} />
        ))}
      </div>
      {!filteredProviders.length ? <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">No providers found.</div> : null}
      <NamedConnectionDialog onOpenChange={setDialogProvider} provider={dialogProvider} />
    </div>
  );
}

function ProviderCard({ onNamedLogin, provider }: { onNamedLogin: () => void; provider: ProviderView }) {
  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-lg bg-muted font-semibold text-primary">
              {provider.logoInitial}
            </span>
            <div>
              <CardTitle className="text-base">{provider.displayName}</CardTitle>
              <CardDescription>{provider.name}</CardDescription>
            </div>
          </div>
          <StatusBadge status={provider.status} />
        </div>
      </CardHeader>
      <CardContent className="grid gap-4">
        <p className="min-h-10 text-sm text-muted-foreground">{provider.description || provider.apiUrl}</p>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">{provider.authTypeLabel}</Badge>
          <Badge variant="secondary">{provider.source}</Badge>
          {provider.connectionCount ? <Badge variant="outline">{provider.connectionCount} connections</Badge> : null}
        </div>
        {provider.requiresNamedLogin ? (
          <Button onClick={onNamedLogin} type="button" variant="secondary">
            <LogIn />
            Login
          </Button>
        ) : (
          <form action={`/auth/providers/${provider.name}/connect`} method="post">
            <input name="connection" type="hidden" value="default" />
            <input name="return_url" type="hidden" value={NEXT_URL} />
            <Button className="w-full" type="submit" variant="secondary">
              <LogIn />
              Login
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

function NamedConnectionDialog({
  onOpenChange,
  provider,
}: {
  onOpenChange: (provider: ProviderView | null) => void;
  provider: ProviderView | null;
}) {
  const [connectionName, setConnectionName] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    if (!connectionName.trim()) {
      event.preventDefault();
    }
  }

  return (
    <Dialog open={Boolean(provider)} onOpenChange={(open) => onOpenChange(open ? provider : null)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connection name</DialogTitle>
          <DialogDescription>{provider?.displayName} already has a default connection.</DialogDescription>
        </DialogHeader>
        <form
          action={provider ? `/auth/providers/${provider.name}/connect` : "#"}
          className="grid gap-4"
          method="post"
          onSubmit={handleSubmit}
        >
          <input name="return_url" type="hidden" value={NEXT_URL} />
          <label className="grid gap-2 text-sm">
            <span className="text-muted-foreground">Connection name</span>
            <Input
              autoFocus
              name="connection_name"
              onChange={(event) => setConnectionName(event.target.value)}
              required
              value={connectionName}
            />
          </label>
          <DialogFooter>
            <DialogClose render={<Button type="button" variant="outline" />}>Cancel</DialogClose>
            <Button type="submit">Continue</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ConnectionsView({ connections }: { connections: DashboardData["connections"] }) {
  const [query, setQuery] = useState("");
  const filteredConnections = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return connections;
    }
    return connections.filter((row) =>
      `${row.connectionName} ${row.providerDisplayName} ${row.authTypeLabel}`.toLowerCase().includes(normalized),
    );
  }, [connections, query]);

  return (
    <div className="grid gap-5">
      <SectionHeader description="Named connections in the current vault." title="Connections" />
      <SearchInput onChange={setQuery} placeholder="Search connections..." value={query} />
      <Card className="shadow-none border-border/50">
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
                {filteredConnections.map((row) => (
                  <TableRow key={`${row.providerName}:${row.connectionName}`}>
                    <TableCell className="font-medium">{row.connectionName}</TableCell>
                    <TableCell>{row.providerDisplayName}</TableCell>
                    <TableCell>{row.authTypeLabel}</TableCell>
                    <TableCell>
                      <StatusBadge status={row.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground">No connections found.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function VaultView({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Credential namespace and claimed identities." title="Vault" />
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle>Default Vault</CardTitle>
            <CardDescription>{data.vault.isDefault ? "Active for this account" : "Vault binding"}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <KeyValue label="Handle" value={data.vault.handle} />
            <KeyValue label="Vault ID" value={data.vault.vaultId || "-"} />
          </CardContent>
        </Card>
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle>Identities</CardTitle>
            <CardDescription>Claims accepted for this account.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            {data.identities.map((identity) => (
              <div className="flex items-center justify-between rounded-lg border bg-muted p-3" key={identity.handle}>
                <div className="flex items-center gap-3">
                  <UserRound className="size-4 text-muted-foreground" />
                  <span className="font-medium">{identity.handle}</span>
                </div>
                {identity.isActive ? <Badge variant="outline">Active</Badge> : null}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AuditView({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Recent administrative and credential events." title="Audit Log" />
      <Card className="shadow-none border-border/50">
        <CardContent className="p-0">
          {data.audit.events.length ? (
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
                {data.audit.events.map((event) => (
                  <TableRow key={event.eventId}>
                    <TableCell className="whitespace-nowrap">{event.time}</TableCell>
                    <TableCell className="font-medium">{event.event}</TableCell>
                    <TableCell>{event.actor}</TableCell>
                    <TableCell>{event.target}</TableCell>
                    <TableCell>{event.status}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground">No audit events found.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SettingsView({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Local daemon and package context." title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <KeyValue label="Email" value={data.account.email || "-"} />
            <KeyValue label="Role" value={data.account.roleLabel || "-"} />
            <AdvancedSection>
              <KeyValue label="Principal ID" value={data.account.principalId || "-"} />
            </AdvancedSection>
          </CardContent>
        </Card>
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle>Daemon</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <KeyValue label="Version" value={data.version} />
            <AdvancedSection>
              <KeyValue label="UI Path" value="/" />
            </AdvancedSection>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}


function AdvancedSection({ children }: { children: ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <div className="grid gap-2 mt-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShow(!show)}
        className="w-max -ml-2 h-8 text-xs text-muted-foreground"
        type="button"
      >
        {show ? "Hide advanced" : "Show advanced"}
      </Button>
      {show && <div className="grid gap-4 animate-in fade-in slide-in-from-top-1">{children}</div>}
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1">
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      <Tooltip>
        <TooltipTrigger render={<div className="truncate rounded-lg border bg-muted px-3 py-2 font-mono text-sm" />}>
          {value}
        </TooltipTrigger>
        <TooltipContent>{value}</TooltipContent>
      </Tooltip>
    </div>
  );
}

function SectionHeader({ description, title }: { description: string; title: string }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold leading-tight text-foreground">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

function SearchInput({
  onChange,
  placeholder,
  value,
}: {
  onChange: (value: string) => void;
  placeholder: string;
  value: string;
}) {
  return (
    <label className="relative block max-w-md">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input className="h-9 pl-9" onChange={(event) => onChange(event.target.value)} placeholder={placeholder} value={value} />
    </label>
  );
}

function ActiveView({
  data,
  onViewChange,
  view,
}: {
  data: DashboardData;
  onViewChange: (view: View) => void;
  view: View;
}) {
  if (view === "providers") {
    return <ProvidersView providers={data.providers} />;
  }
  if (view === "connections") {
    return <ConnectionsView connections={data.connections} />;
  }
  if (view === "vault") {
    return <VaultView data={data} />;
  }
  if (view === "audit" && data.account.isAdmin) {
    return <AuditView data={data} />;
  }
  if (view === "settings") {
    return <SettingsView data={data} />;
  }
  return <DashboardView data={data} onViewChange={onViewChange} />;
}

export function AuthsomeDashboard() {
  const [activeView, setActiveView] = useState<View>("dashboard");
  const { data, error, mutate } = useSWR("authsome-dashboard", fetchDashboard, {
    dedupingInterval: 10_000,
    revalidateOnFocus: true,
  });

  if (isUnauthorized(error)) {
    return <AuthGate />;
  }
  if (error) {
    return <ErrorState onRetry={() => void mutate()} />;
  }
  if (!data) {
    return <LoadingScreen />;
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="md:grid md:grid-cols-[256px_1fr]">
        <Sidebar activeView={activeView} data={data} onChange={setActiveView} />
        <section className="min-w-0">
          <Topbar />
          <div className="mx-auto grid max-w-7xl gap-6 p-4 md:p-6">
            <div className="flex items-center justify-between gap-3">
              <div className="md:hidden">
                <div className="text-lg font-semibold">Authsome</div>
                <div className="text-xs text-muted-foreground">v{data.version}</div>
              </div>
              <Button onClick={() => void mutate()} size="sm" type="button" variant="outline">
                <RefreshCw />
                Refresh
              </Button>
            </div>
            <Separator />
            <ActiveView data={data} onViewChange={setActiveView} view={activeView} />
          </div>
        </section>
      </div>
    </main>
  );
}
