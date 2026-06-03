"use client";

import {
  AppWindow,
  BookOpen,
  CheckCircle2,
  CircleAlert,
  ClipboardList,
  Database,
  GitBranch,
  KeyRound,
  LifeBuoy,
  Link2,
  LogIn,
  LogOut,
  Plus,
  Search,
  Settings,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import useSWR from "swr";

import {
  ApiError,
  DashboardData,
  ProviderView,
  SessionInputField,
  fetchAuthSessionStatus,
  fetchClaimStatus,
  fetchDashboard,
  fetchSessionDevice,
  fetchSessionInput,
} from "@/lib/authsome-api";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type View = "dashboard" | "providers" | "connections" | "identities" | "vault" | "audit" | "settings";

type NavItem = {
  id: View;
  href: string;
  label: string;
  icon: ReactNode;
  adminOnly?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { id: "dashboard", href: "/", label: "Dashboard", icon: <AppWindow /> },
  { id: "providers", href: "/providers", label: "Providers", icon: <KeyRound /> },
  { id: "connections", href: "/connections", label: "Connections", icon: <Link2 /> },
  { id: "identities", href: "/identities", label: "Identities", icon: <UserRound /> },
  { id: "vault", href: "/vault", label: "Vault", icon: <Database /> },
  { id: "audit", href: "/audit", label: "Audit Log", icon: <ClipboardList />, adminOnly: true },
  { id: "settings", href: "/settings", label: "Settings", icon: <Settings /> },
];

const NEXT_URL = "/";
const ADVANCED_SESSION_FIELD_NAMES = new Set(["host_url", "base_url", "api_url", "scopes"]);

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function extractDomain(apiUrl: string): string | null {
  try {
    const url = apiUrl.startsWith("http") ? apiUrl : `https://${apiUrl}`;
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

function ProviderLogo({
  apiUrl,
  initial,
  className,
}: {
  apiUrl: string;
  initial: string;
  className?: string;
}) {
  const [err, setErr] = useState(false);
  const domain = extractDomain(apiUrl);
  const faviconUrl = domain && !err ? `https://www.google.com/s2/favicons?domain=${domain}&sz=64` : null;

  return (
    <span
      className={cn(
        "flex items-center justify-center rounded-lg bg-muted",
        !faviconUrl && "font-semibold text-primary",
        className,
      )}
    >
      {faviconUrl ? (
        <img alt="" className="size-5" onError={() => setErr(true)} src={faviconUrl} />
      ) : (
        initial
      )}
    </span>
  );
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
  return null;
}

function currentBrowserPath(fallback: string): string {
  if (typeof window === "undefined") {
    return fallback;
  }
  return `${window.location.pathname}${window.location.search}`;
}

export function AuthsomeLogin({ nextPath = NEXT_URL }: { nextPath?: string }) {
  const [safeNextPath] = useState(() => {
    if (typeof window === "undefined") {
      return nextPath;
    }
    const next = new URLSearchParams(window.location.search).get("next") || nextPath;
    return next.startsWith("/") && !next.startsWith("//") ? next : NEXT_URL;
  });

  return (
    <main className="flex min-h-screen items-center bg-background px-4 py-8 sm:px-6 lg:px-10">
      <section className="mx-auto grid w-full max-w-6xl gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
        <div className="max-w-md">
          <div>
            <img alt="Authsome" className="mb-8 size-11" src="/logo.svg" />
            <h1 className="text-4xl font-semibold leading-tight text-foreground">
              Authsome
            </h1>
            <p className="mt-4 text-base leading-7 text-muted-foreground">
              Sign in to manage account access, connected providers, and credential vaults.
            </p>
          </div>
        </div>

        <div>
          <Card className="border-border/70 shadow-none">
            <CardHeader>
              <CardTitle>Open Dashboard</CardTitle>
              <CardDescription>Use your Authsome account to continue.</CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs className="gap-6" defaultValue="signin">
                <TabsList className="grid h-9 w-full grid-cols-2">
                  <TabsTrigger value="signin">Sign in</TabsTrigger>
                  <TabsTrigger value="create">Create account</TabsTrigger>
                </TabsList>
                <TabsContent className="grid gap-5" value="signin">
                  <div>
                    <h2 className="text-base font-semibold">Sign in</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Continue with an existing Authsome account.
                    </p>
                  </div>
                  <AccountForm
                    action="/api/auth/login"
                    autoComplete="current-password"
                    nextPath={safeNextPath}
                    submitIcon="login"
                    submitLabel="Sign in"
                  />
                </TabsContent>
                <TabsContent className="grid gap-5" value="create">
                  <div>
                    <h2 className="text-base font-semibold">Create account</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Set up a new account for this dashboard.
                    </p>
                  </div>
                  <AccountForm
                    action="/api/auth/register"
                    autoComplete="new-password"
                    nextPath={safeNextPath}
                    submitIcon="plus"
                    submitLabel="Create account"
                  />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </section>
    </main>
  );
}

export function AuthsomeClaim({ token }: { token: string }) {
  const { data, error } = useSWR(token ? ["authsome-claim", token] : null, () => fetchClaimStatus(token));
  const nextPath = token ? `/claim?token=${encodeURIComponent(token)}` : "/claim";

  if (!token) {
    return (
      <ClaimShell
        description="The claim link is missing a token."
        title="Invalid claim link"
      />
    );
  }

  if (error) {
    return (
      <ClaimShell
        description="This claim link could not be loaded. Request a new link from the CLI."
        title="Claim unavailable"
      />
    );
  }

  if (!data) {
    return (
      <ClaimShell
        description="Checking this identity claim."
        title="Loading claim"
      />
    );
  }

  if (data.expired) {
    return (
      <ClaimShell
        description="This claim link has expired. Request a new link from the CLI."
        title="Claim expired"
      />
    );
  }

  if (!data.authenticated) {
    return <AuthsomeLogin nextPath={nextPath} />;
  }

  return (
    <ClaimShell
      description={`Confirm that ${data.identity} should be linked to ${data.email || "this account"}.`}
      title="Claim identity"
    >
      <form action={`/api/claim/${encodeURIComponent(token)}/confirm`} method="post">
        <Button className="w-full" type="submit">
          <UserRound />
          Confirm claim
        </Button>
      </form>
    </ClaimShell>
  );
}

export function AuthsomeClaimFromUrl() {
  const searchParams = useSearchParams();
  return <AuthsomeClaim token={searchParams.get("token") || ""} />;
}

export function AuthsomeSessionInputFromUrl() {
  const searchParams = useSearchParams();
  return <AuthsomeSessionInput sessionId={searchParams.get("session") || ""} />;
}

export function AuthsomeSessionDeviceFromUrl() {
  const searchParams = useSearchParams();
  return <AuthsomeSessionDevice sessionId={searchParams.get("session") || ""} />;
}

export function AuthsomeSessionSuccessFromUrl() {
  const searchParams = useSearchParams();
  return (
    <AuthsomeSessionSuccess
      errorCode={searchParams.get("error") || ""}
      sessionId={searchParams.get("session") || ""}
    />
  );
}

function AuthsomeSessionInput({ sessionId }: { sessionId: string }) {
  const { data, error } = useSWR(sessionId ? ["authsome-session-input", sessionId] : null, () =>
    fetchSessionInput(sessionId),
  );

  if (!sessionId) {
    return (
      <ClaimShell
        description="The provider setup link is missing a session identifier."
        title="Invalid setup link"
      />
    );
  }

  if (error) {
    return (
      <ClaimShell
        description="This provider setup session could not be loaded. Start the login flow again."
        title="Setup unavailable"
      />
    );
  }

  if (!data) {
    return (
      <ClaimShell
        description="Loading the provider setup fields."
        title="Loading setup"
      />
    );
  }

  const primaryFields = data.fields.filter((field) => !ADVANCED_SESSION_FIELD_NAMES.has(field.name));
  const advancedFields = data.fields.filter((field) => ADVANCED_SESSION_FIELD_NAMES.has(field.name));

  return (
    <ClaimShell
      description="Enter the provider details required to continue this login flow."
      title={data.display_name}
    >
      <form action={`/auth/input?session=${encodeURIComponent(sessionId)}`} className="grid gap-4" method="post">
        {data.warning ? (
          <div className="rounded-lg border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
            {data.warning}
          </div>
        ) : null}
        {data.callback_url ? (
          <label className="grid gap-2 text-sm">
            <span className="text-muted-foreground">OAuth callback URL</span>
            <Input readOnly value={data.callback_url} />
          </label>
        ) : null}
        {primaryFields.map((field) => (
          <SessionInputFieldControl field={field} key={field.name} />
        ))}
        {advancedFields.length ? (
          <details className="rounded-lg border bg-muted/20 p-3">
            <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
              Advanced
            </summary>
            <div className="mt-4 grid gap-4">
              {advancedFields.map((field) => (
                <SessionInputFieldControl field={field} key={field.name} />
              ))}
            </div>
          </details>
        ) : null}
        <Button className="mt-2 w-full" type="submit">
          <LogIn />
          Continue
        </Button>
      </form>
    </ClaimShell>
  );
}

function SessionInputFieldControl({ field }: { field: SessionInputField }) {
  return (
    <label className="grid gap-2 text-sm">
      <span className="text-muted-foreground">{field.label}</span>
      <Input
        defaultValue={field.default || ""}
        name={field.name}
        pattern={field.pattern || undefined}
        required
        type={field.secret ? "password" : "text"}
      />
      {field.pattern_hint ? (
        <span className="text-xs text-muted-foreground">{field.pattern_hint}</span>
      ) : null}
    </label>
  );
}

function AuthsomeSessionSuccess({ errorCode, sessionId }: { errorCode?: string; sessionId: string }) {
  const { data, error } = useSWR(sessionId ? ["authsome-session-status", sessionId] : null, () =>
    fetchAuthSessionStatus(sessionId),
  );

  if (errorCode) {
    const description =
      errorCode === "session_expired"
        ? "This authentication session expired. Start the login flow again."
        : "The provider callback did not include a valid authentication state.";
    return (
      <ClaimShell
        description={description}
        title="Login could not finish"
      />
    );
  }

  if (!sessionId) {
    return (
      <ClaimShell
        description="The completion link is missing a session identifier."
        title="Invalid session"
      />
    );
  }

  if (error) {
    return (
      <ClaimShell
        description="This login session could not be loaded. Check the terminal for the latest status."
        title="Session unavailable"
      />
    );
  }

  if (!data) {
    return (
      <ClaimShell
        description="Checking the latest login status."
        title="Finishing login"
      />
    );
  }

  const isCompleted = data.status === "completed";
  const isFailed = data.status === "failed";
  const title = isCompleted ? "Login complete" : isFailed ? "Login failed" : "Login in progress";
  const description = isCompleted
    ? `${data.provider} is connected as ${data.connection}.`
    : isFailed
      ? data.error || "The provider reported an authentication error."
      : data.message || "This provider is still finishing authentication.";

  return (
    <ClaimShell description={description} title={title}>
      <div className="grid gap-5">
        <div className="flex items-center gap-3 rounded-lg border bg-muted/25 px-4 py-3">
          <div
            className={cn(
              "flex size-10 shrink-0 items-center justify-center rounded-lg border",
              isCompleted
                ? "border-emerald-800 bg-emerald-950/50 text-emerald-400"
                : isFailed
                  ? "border-destructive/40 bg-destructive/10 text-destructive"
                  : "border-amber-800 bg-amber-950/40 text-amber-400",
            )}
          >
            {isCompleted ? <CheckCircle2 /> : <CircleAlert />}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{data.provider}</p>
            <p className="truncate text-xs text-muted-foreground">{data.connection}</p>
          </div>
        </div>
        <Button render={<Link href={isCompleted ? "/connections" : "/"} />}>
          {isCompleted ? "View connection" : "Back to dashboard"}
        </Button>
      </div>
    </ClaimShell>
  );
}

function AuthsomeSessionDevice({ sessionId }: { sessionId: string }) {
  const { data, error } = useSWR(sessionId ? ["authsome-session-device", sessionId] : null, () =>
    fetchSessionDevice(sessionId),
  );

  if (!sessionId) {
    return (
      <ClaimShell
        description="The device-code link is missing a session identifier."
        title="Invalid device link"
      />
    );
  }

  if (error) {
    return (
      <ClaimShell
        description="This device-code session could not be loaded. Start the login flow again."
        title="Device login unavailable"
      />
    );
  }

  if (!data) {
    return (
      <ClaimShell
        description="Loading the device-code login details."
        title="Loading device login"
      />
    );
  }

  return (
    <ClaimShell
      description={`Use this code to finish signing in to ${data.display_name}.`}
      title="Device login"
    >
      <div className="grid gap-4">
        <div className="rounded-lg border bg-muted/30 px-4 py-3 text-center font-mono text-2xl font-semibold">
          {data.user_code}
        </div>
        <Button
          render={<a href={data.verification_uri_complete || data.verification_uri} rel="noreferrer" target="_blank" />}
          type="button"
        >
          Open verification page
        </Button>
      </div>
    </ClaimShell>
  );
}

function ClaimShell({
  children,
  description,
  title,
}: {
  children?: ReactNode;
  description: string;
  title: string;
}) {
  return (
    <main className="flex min-h-screen items-center bg-background px-4 py-8 sm:px-6 lg:px-10">
      <section className="mx-auto w-full max-w-md">
        <Card className="border-border/70 shadow-none">
          <CardHeader>
            <img alt="Authsome" className="mb-4 size-9" src="/logo.svg" />
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          {children ? <CardContent>{children}</CardContent> : null}
        </Card>
      </section>
    </main>
  );
}

function AccountForm({
  action,
  autoComplete,
  nextPath,
  submitIcon,
  submitLabel,
}: {
  action: string;
  autoComplete: "current-password" | "new-password";
  nextPath: string;
  submitIcon: "login" | "plus";
  submitLabel: string;
}) {
  return (
    <form action={action} className="grid gap-4" method="post">
      <input name="next" type="hidden" value={nextPath} />
      <label className="grid gap-2 text-sm">
        <span className="text-muted-foreground">Email</span>
        <Input autoComplete="email" name="email" required type="email" />
      </label>
      <label className="grid gap-2 text-sm">
        <span className="text-muted-foreground">Password</span>
        <Input autoComplete={autoComplete} minLength={8} name="password" required type="password" />
      </label>
      <Button className="mt-2 w-full" type="submit" variant={submitIcon === "plus" ? "outline" : "default"}>
        {submitIcon === "plus" ? <Plus /> : <LogIn />}
        {submitLabel}
      </Button>
    </form>
  );
}

function LoadingScreen() {
  return (
    <main className="grid min-h-screen grid-cols-1 bg-background md:grid-cols-[240px_1fr]">
      <aside className="hidden border-r bg-card p-5 md:block">
        <Skeleton className="h-8 w-36" />
        <div className="mt-8 grid gap-3">
          {Array.from({ length: 7 }).map((_, index) => (
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
}: {
  activeView: View;
  data: DashboardData;
}) {
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || data.account.isAdmin);

  return (
    <aside className="flex border-r bg-sidebar md:min-h-screen md:w-64 md:flex-col">
      <div className="hidden border-b px-5 py-4 md:block">
        <div className="flex items-center gap-2">
          <img alt="Authsome" className="size-7" src="/logo.svg" />
          <span className="text-sm font-semibold">Authsome</span>
        </div>
      </div>
      <ScrollArea className="w-full md:flex-1">
        <nav className="flex gap-1 overflow-x-auto p-3 md:grid md:gap-1 md:overflow-visible">
          {items.map((item) => (
            <Link
              className={cn(
                "inline-flex h-9 shrink-0 items-center gap-2 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:w-full",
                activeView === item.id && "bg-sidebar-accent text-sidebar-accent-foreground",
              )}
              href={item.href}
              key={item.id}
            >
              <span className="[&_svg]:size-4">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>
      </ScrollArea>
      <div className="hidden border-t md:block">
        <div className="border-b px-4 py-3">
          <div className="truncate text-sm font-medium">{data.account.email || data.account.identity}</div>
          {data.account.roleLabel ? (
            <div className="mt-0.5 text-xs text-muted-foreground">{data.account.roleLabel}</div>
          ) : null}
        </div>
        <nav className="grid gap-1 p-3">
          <a
            className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            href="https://authsome.ai/docs"
            rel="noreferrer"
            target="_blank"
          >
            <BookOpen className="size-4" />
            Docs
          </a>
          <a
            className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            href="https://github.com/agentrhq/authsome"
            rel="noreferrer"
            target="_blank"
          >
            <GitBranch className="size-4" />
            GitHub
          </a>
          <a
            className="inline-flex h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            href="https://authsome.ai/support"
            rel="noreferrer"
            target="_blank"
          >
            <LifeBuoy className="size-4" />
            Support
          </a>
        </nav>
      </div>
    </aside>
  );
}

function Topbar() {
  return (
    <header className="flex min-h-14 items-center justify-end gap-3 border-b bg-card px-4 py-3 md:px-6">
      <form action="/api/logout" method="post">
        <input name="return_url" type="hidden" value={NEXT_URL} />
        <Button size="sm" type="submit" variant="ghost">
          <LogOut />
          Sign out
        </Button>
      </form>
    </header>
  );
}

function DashboardView({ data }: { data: DashboardData }) {
  const recentEvents = data.audit.events.slice(0, 5);

  return (
    <div className="grid gap-8">
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold">Connected Apps</h2>
          <Button render={<Link href="/providers" />} size="sm" variant="outline">
            Browse
          </Button>
        </div>
        {data.connectedProviders.length ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.connectedProviders.map((provider) => (
              <ProviderSummary key={provider.name} provider={provider} />
            ))}
          </div>
        ) : (
          <EmptyBlock
            actionLabel="Browse providers"
            href="/providers"
            title="No connections yet"
          />
        )}
      </section>

      <section>
        <div className="mb-4">
          <h2 className="text-base font-semibold">Identities</h2>
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
          <div className="rounded-lg border border-dashed bg-muted/50 p-6 text-center text-sm text-muted-foreground">
            No identities found.
          </div>
        )}
      </section>

      {data.audit.canView && recentEvents.length > 0 ? (
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Recent Events</h2>
            <Button render={<Link href="/audit" />} size="sm" variant="ghost">
              View all
            </Button>
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

function ProviderSummary({ provider }: { provider: ProviderView }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 px-4 py-3">
      <div className="flex items-center gap-3">
        <ProviderLogo apiUrl={provider.apiUrl} className="size-8" initial={provider.logoInitial} />
        <div>
          <div className="text-sm font-medium">{provider.displayName}</div>
          <div className="text-xs text-muted-foreground">{provider.authTypeLabel}</div>
        </div>
      </div>
      <StatusBadge status={provider.status} />
    </div>
  );
}

function EmptyBlock({ actionLabel, href, title }: { actionLabel: string; href: string; title: string }) {
  return (
    <div className="rounded-lg border border-dashed bg-muted/50 p-6 text-center">
      <div className="font-medium">{title}</div>
      <Button className="mt-4" render={<Link href={href} />} size="sm">
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
    if (!normalized) return providers;
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
      {!filteredProviders.length ? (
        <div className="rounded-lg border bg-card p-8 text-center text-muted-foreground">No providers found.</div>
      ) : null}
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
            <ProviderLogo apiUrl={provider.apiUrl} className="size-10" initial={provider.logoInitial} />
            <div>
              <CardTitle className="text-base">{provider.displayName}</CardTitle>
              <CardDescription className="text-xs">{provider.authTypeLabel}</CardDescription>
            </div>
          </div>
          <StatusBadge status={provider.status} />
        </div>
      </CardHeader>
      <CardContent className="grid gap-4">
        {provider.description ? (
          <p className="min-h-8 text-sm text-muted-foreground">{provider.description}</p>
        ) : null}
        {provider.connectionCount ? (
          <Badge className="w-max" variant="outline">{provider.connectionCount} connection{provider.connectionCount !== 1 ? "s" : ""}</Badge>
        ) : null}
        {provider.requiresNamedLogin ? (
          <Button className="w-full" onClick={onNamedLogin} type="button">
            <LogIn />
            Login
          </Button>
        ) : (
          <form action={`/api/auth/providers/${provider.name}/connect`} method="post">
            <input name="connection" type="hidden" value="default" />
            <input name="return_url" type="hidden" value={`/connections?provider=${provider.name}`} />
            <Button className="w-full" type="submit">
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
          action={provider ? `/api/auth/providers/${provider.name}/connect` : "#"}
          className="grid gap-4"
          method="post"
          onSubmit={handleSubmit}
        >
          <input name="return_url" type="hidden" value={provider ? `/connections?provider=${provider.name}` : NEXT_URL} />
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

function ConnectionsView({
  connections,
  initialFilter,
}: {
  connections: DashboardData["connections"];
  initialFilter?: string;
}) {
  const [query, setQuery] = useState(() => {
    if (initialFilter) {
      return initialFilter;
    }
    if (typeof window === "undefined") {
      return "";
    }
    return new URLSearchParams(window.location.search).get("provider") ?? "";
  });
  const filteredConnections = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return connections;
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

function IdentitiesView({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Local Ed25519 key pairs claimed to this account." title="Identities" />
      <div className="grid gap-3">
        {data.identities.length ? (
          data.identities.map((identity) => (
            <div
              className="flex items-center justify-between rounded-lg border bg-card px-4 py-4"
              key={identity.handle}
            >
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg bg-muted">
                  <UserRound className="size-4 text-muted-foreground" />
                </span>
                <div>
                  <div className="font-medium">{identity.handle}</div>
                </div>
              </div>
              {identity.isActive ? <Badge variant="outline">Active</Badge> : null}
            </div>
          ))
        ) : (
          <div className="rounded-lg border border-dashed bg-muted/50 p-8 text-center text-muted-foreground">
            No identities found.
          </div>
        )}
      </div>
    </div>
  );
}

function VaultView({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Credential namespace for this account." title="Vault" />
      <Card className="shadow-none border-border/50 max-w-md">
        <CardHeader>
          <CardTitle>Default Vault</CardTitle>
          <CardDescription>{data.vault.isDefault ? "Active for this account" : "Vault binding"}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <KeyValue label="Handle" value={data.vault.handle} />
          <KeyValue label="Vault ID" value={data.vault.vaultId || "-"} />
          <KeyValue label="Principal ID" value={data.account.principalId || "-"} />
        </CardContent>
      </Card>
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
      <SectionHeader description="Local daemon and account context." title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <KeyValue label="Email" value={data.account.email || "-"} />
            <KeyValue label="Role" value={data.account.roleLabel || "-"} />
            <KeyValue label="Principal ID" value={data.account.principalId || "-"} />
          </CardContent>
        </Card>
        <Card className="shadow-none border-border/50">
          <CardHeader>
            <CardTitle>Daemon</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <KeyValue label="Version" value={data.version} />
            <KeyValue label="Encryption" value={data.account.principalId ? "AES-256-GCM" : "-"} />
          </CardContent>
        </Card>
      </div>
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
      <Input
        className="h-9 pl-9"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        value={value}
      />
    </label>
  );
}

function ActiveView({ connectionFilter, data, view }: {
  connectionFilter?: string;
  data: DashboardData;
  view: View;
}) {
  if (view === "providers") return <ProvidersView providers={data.providers} />;
  if (view === "connections") return <ConnectionsView connections={data.connections} initialFilter={connectionFilter} />;
  if (view === "identities") return <IdentitiesView data={data} />;
  if (view === "vault") return <VaultView data={data} />;
  if (view === "audit" && data.account.isAdmin) return <AuditView data={data} />;
  if (view === "settings") return <SettingsView data={data} />;
  return <DashboardView data={data} />;
}

export function AuthsomeDashboard({ connectionFilter, view = "dashboard" }: { connectionFilter?: string; view?: View }) {
  const pathname = usePathname();
  const router = useRouter();
  const activeView = NAV_ITEMS.some((item) => item.id === view) ? view : "dashboard";
  const { data, error, mutate } = useSWR("authsome-dashboard", fetchDashboard, {
    dedupingInterval: 10_000,
    revalidateOnFocus: true,
  });

  useEffect(() => {
    if (isUnauthorized(error)) {
      router.replace(`/login?next=${encodeURIComponent(currentBrowserPath(pathname || NEXT_URL))}`);
    }
  }, [error, pathname, router]);

  if (isUnauthorized(error)) return <LoadingScreen />;
  if (error) return <ErrorState onRetry={() => void mutate()} />;
  if (!data) return <LoadingScreen />;

  return (
    <main className="min-h-screen bg-background">
      <div className="md:grid md:grid-cols-[256px_1fr]">
        <Sidebar activeView={activeView} data={data} />
        <section className="min-w-0">
          <Topbar />
          <div className="mx-auto grid max-w-7xl gap-6 p-4 md:p-6">
            <ActiveView
              connectionFilter={connectionFilter}
              data={data}
              view={activeView}
            />
          </div>
        </section>
      </div>
    </main>
  );
}
