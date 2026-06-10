"use client";

import {
  AppWindow,
  BookOpen,
  Check,
  CheckCircle2,
  CircleAlert,
  Clipboard,
  ClipboardList,
  Database,
  GitBranch,
  Globe2,
  KeyRound,
  LifeBuoy,
  Link2,
  LogIn,
  LogOut,
  Plus,
  Save,
  Search,
  Settings,
  UserRound,
  Users,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import useSWR from "swr";

import {
  ApiError,
  ConnectionDetail,
  DashboardData,
  GlobalConnectionRow,
  PrincipalRow,
  ProviderDetail,
  ProviderView,
  SessionInputField,
  fetchAuthSessionStatus,
  fetchClaimStatus,
  fetchConnectionDetail,
  fetchDashboard,
  fetchPrincipals,
  fetchProviderDetail,
  fetchSessionDevice,
  fetchSessionInput,
  logoutConnection,
  revokeProvider,
  setGlobalConnection,
  unsetGlobalConnection,
  updateProviderConfiguration,
} from "@/lib/authsome-api";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type View = "dashboard" | "providers" | "connections" | "agents" | "principals" | "vault" | "audit" | "settings";

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
  { id: "agents", href: "/agents", label: "Agents", icon: <UserRound /> },
  { id: "principals", href: "/principal", label: "Principals", icon: <Users />, adminOnly: true },
  { id: "vault", href: "/vault", label: "Vault", icon: <Database /> },
  { id: "audit", href: "/audit", label: "Audit Log", icon: <ClipboardList />, adminOnly: true },
  { id: "settings", href: "/settings", label: "Settings", icon: <Settings /> },
];

const NEXT_URL = "/";
const ADVANCED_SESSION_FIELD_NAMES = new Set(["host_url", "base_url", "api_url", "scopes"]);
const LOGO_DEV_TOKEN = "pk_BhJg_kBbQPqNGuuWcNs9Cg";

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function ProviderLogo({
  initial,
  logo,
  className,
}: {
  initial: string;
  logo: string | null;
  className?: string;
}) {
  const [err, setErr] = useState(false);
  const logoUrl = logo && !err ? providerLogoUrl(logo) : null;

  return (
    <span
      className={cn(
        "flex items-center justify-center rounded-lg border border-border/60 bg-muted text-sm font-semibold text-primary",
        className,
      )}
    >
      {logoUrl ? (
        <Image
          alt=""
          className="size-5 object-contain"
          height={20}
          onError={() => setErr(true)}
          src={logoUrl}
          unoptimized
          width={20}
        />
      ) : (
        initial
      )}
    </span>
  );
}

function providerLogoUrl(logo: string): string {
  if (logo.startsWith("http")) {
    return logo;
  }
  if (logo.startsWith("img.logo.dev")) {
    return `https://${logo}?token=${LOGO_DEV_TOKEN}`;
  }
  return logo;
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

export function currentBrowserPath(fallback: string): string {
  if (typeof window === "undefined") {
    return fallback;
  }
  return `${window.location.pathname}${window.location.search}`;
}

function connectionDetailHref(provider: string, connection: string, principal?: string | null): string {
  const params = new URLSearchParams({ provider, connection });
  if (principal) {
    params.set("principal", principal);
  }
  return `/connections/detail?${params.toString()}`;
}

function providerDetailHref(provider: string): string {
  return `/providers/detail?${new URLSearchParams({ provider }).toString()}`;
}

export function AuthsomeLogin({ nextPath = NEXT_URL }: { nextPath?: string }) {
  const [safeNextPath] = useState(() => {
    if (typeof window === "undefined") {
      return nextPath;
    }
    const next = new URLSearchParams(window.location.search).get("next") || nextPath;
    return next.startsWith("/") && !next.startsWith("//") ? next : NEXT_URL;
  });

  const [errorMessage] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("error") || "";
  });

  const [defaultTab] = useState(() => {
    if (typeof window === "undefined") return "signin";
    const tab = new URLSearchParams(window.location.search).get("tab");
    return tab === "register" ? "create" : "signin";
  });

  return (
    <main className="flex min-h-screen items-center bg-background px-4 py-8 sm:px-6 lg:px-10">
      <section className="mx-auto grid w-full max-w-6xl gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
        <div className="max-w-md">
          <div>
            <Image alt="Authsome" className="mb-8 size-11" height={44} src="/logo.svg" width={44} />
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
              <Tabs className="gap-6" defaultValue={defaultTab}>
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
                  {defaultTab === "signin" && errorMessage ? (
                    <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      <CircleAlert className="size-4 shrink-0" />
                      {errorMessage}
                    </div>
                  ) : null}
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
                  {defaultTab === "create" && errorMessage ? (
                    <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      <CircleAlert className="size-4 shrink-0" />
                      {errorMessage}
                    </div>
                  ) : null}
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
        required={field.required !== false}
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
        <Link className={buttonVariants()} href={isCompleted ? "/connections" : "/"}>
          {isCompleted ? "View connection" : "Back to dashboard"}
        </Link>
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
        <Link
          className={buttonVariants()}
          href={data.verification_uri_complete || data.verification_uri}
          rel="noreferrer"
          target="_blank"
        >
          Open verification page
        </Link>
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
            <Image alt="Authsome" className="mb-4 size-9" height={36} src="/logo.svg" width={36} />
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

export function LoadingScreen() {
  return (
    <SidebarProvider>
      <Sidebar collapsible="offcanvas">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <Skeleton className="h-9 w-full rounded-md" />
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {Array.from({ length: 7 }).map((_, i) => (
                  <SidebarMenuSkeleton key={i} showIcon />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>
      <SidebarInset>
        <header className="flex h-14 items-center border-b px-4">
          <Skeleton className="size-8 rounded-md" />
        </header>
        <section className="p-6">
          <Skeleton className="h-10 w-56" />
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton className="h-32 rounded-lg" key={i} />
            ))}
          </div>
        </section>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function ErrorState({ onRetry }: { onRetry: () => void }) {
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

function DashboardDetailShell({
  activeView,
  children,
  data,
}: {
  activeView: View;
  children: ReactNode;
  data: DashboardData;
}) {
  return (
    <SidebarProvider className="h-svh overflow-hidden">
      <AppSidebar activeView={activeView} data={data} />
      <SidebarInset className="min-h-0">
        <Topbar />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid w-full max-w-[86rem] gap-6 p-4 md:p-6">
            {children}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function AppSidebar({
  activeView,
  data,
}: {
  activeView: View;
  data: DashboardData;
}) {
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || data.account.isAdmin);

  return (
    <Sidebar collapsible="offcanvas">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link href="/" />}>
              <Image alt="Authsome" className="size-5 shrink-0" height={20} src="/logo.svg" width={20} />
              <span className="font-semibold">Authsome</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    render={<Link href={item.href} />}
                    isActive={activeView === item.id}
                    tooltip={item.label}
                  >
                    {item.icon}
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton render={<Link href="https://authsome.ai/docs" rel="noreferrer" target="_blank" />}>
              <BookOpen />
              <span>Docs</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton render={<Link href="https://github.com/agentrhq/authsome" rel="noreferrer" target="_blank" />}>
              <GitBranch />
              <span>GitHub</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton render={<Link href="https://authsome.ai/support" rel="noreferrer" target="_blank" />}>
              <LifeBuoy />
              <span>Support</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarSeparator />
        <div className="px-2 py-1">
          <div className="truncate text-sm font-medium">{data.account.email || data.account.identity}</div>
          {data.account.roleLabel ? (
            <div className="mt-0.5 text-xs text-muted-foreground">{data.account.roleLabel}</div>
          ) : null}
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

function Topbar() {
  return (
    <header className="flex min-h-14 items-center justify-between gap-3 border-b bg-card px-4 py-3 md:px-6">
      <SidebarTrigger />
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
          <EmptyBlock
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
          <div className="rounded-lg border border-dashed bg-muted/50 p-6 text-center text-sm text-muted-foreground">
            No identities found.
          </div>
        )}
      </section>

      {data.audit.canView && recentEvents.length > 0 ? (
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Recent Events</h2>
            <Link className={buttonVariants({ size: "sm", variant: "ghost" })} href="/audit">
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

function ProviderSummary({ provider }: { provider: ProviderView }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 px-4 py-3">
      <div className="flex items-center gap-3">
        <ProviderLogo className="size-8" initial={provider.logoInitial} logo={provider.logo} />
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
      <Link className={cn(buttonVariants({ size: "sm" }), "mt-4")} href={href}>
        <Plus />
        {actionLabel}
      </Link>
    </div>
  );
}

export function ProvidersView({ providers }: { providers: ProviderView[] }) {
  const [query, setQuery] = useState("");
  const [dialogProvider, setDialogProvider] = useState<ProviderView | null>(null);

  const filteredProviders = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const matches = normalized
      ? providers.filter((provider) =>
        `${provider.displayName} ${provider.name} ${provider.authTypeLabel} ${provider.description}`
          .toLowerCase()
          .includes(normalized),
      )
      : providers;

    return [...matches].sort((a, b) =>
      providerSortRank(a) - providerSortRank(b)
      || a.displayName.localeCompare(b.displayName),
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

function providerSortRank(provider: ProviderView): number {
  return provider.status === "available" ? 1 : 0;
}

function ProviderCard({ onNamedLogin, provider }: { onNamedLogin: () => void; provider: ProviderView }) {
  const router = useRouter();

  return (
    <Card
      className="flex h-full cursor-pointer flex-col border-border/50 shadow-none transition-all hover:border-border hover:bg-accent hover:shadow-sm"
      onClick={() => router.push(providerDetailHref(provider.name))}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <ProviderLogo className="size-10 shrink-0" initial={provider.logoInitial} logo={provider.logo} />
          <StatusBadge status={provider.status} />
        </div>
        <div className="mt-1">
          <CardTitle className="text-base leading-tight">{provider.displayName}</CardTitle>
          <CardDescription className="mt-0.5 text-xs">
            {provider.source === "custom" ? "Custom provider" : "Bundled provider"}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4 pt-0">
        <p className="line-clamp-2 text-sm leading-relaxed text-muted-foreground">
          {provider.description || "Connect this provider to store and inject credentials from your Authsome vault."}
        </p>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline">{provider.authTypeLabel}</Badge>
          {provider.connectionCount ? (
            <Badge variant="outline">
              {provider.connectionCount} connection{provider.connectionCount !== 1 ? "s" : ""}
            </Badge>
          ) : null}
          {provider.globalConnectionCount ? <Badge variant="outline">Global</Badge> : null}
        </div>
        <div className="mt-auto" onClick={(e) => e.stopPropagation()}>
          {provider.requiresNamedLogin ? (
            <Button
              className="w-full"
              onClick={(e) => { e.preventDefault(); onNamedLogin(); }}
              type="button"
            >
              <LogIn />
              Connect
            </Button>
          ) : (
            <form action={`/api/auth/providers/${provider.name}/connect`} method="post">
              <input name="connection" type="hidden" value="default" />
              <input name="return_url" type="hidden" value={`/connections?provider=${provider.name}`} />
              <Button className="w-full" type="submit">
                <LogIn />
                Connect
              </Button>
            </form>
          )}
        </div>
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
                {filteredConnections.map((row) => (
                  <TableRow key={`${row.providerName}:${row.connectionName}`}>
                    <TableCell>
                      <Link
                        className="font-medium hover:underline underline-offset-4"
                        href={connectionDetailHref(row.providerName, row.connectionName)}
                      >
                        {row.connectionName}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{row.providerDisplayName}</TableCell>
                    <TableCell className="text-muted-foreground">{row.authTypeLabel}</TableCell>
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

function GlobalConnectionsSection({
  connections,
  isAdmin,
  onRefresh,
}: {
  connections: GlobalConnectionRow[];
  isAdmin: boolean;
  onRefresh: () => void;
}) {
  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <CardTitle>Global Connections</CardTitle>
        <CardDescription>Deployment-wide fallback connections available to accepted identities.</CardDescription>
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
              {connections.map((row) => (
                <TableRow key={`${row.providerName}:${row.connectionName}`}>
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
                    <TableCell>
                      <RemoveGlobalConnectionButton onRefresh={onRefresh} provider={row.providerName} />
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div className="p-8 text-center text-muted-foreground">No global connections found.</div>
        )}
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
                  <TableHead>Status</TableHead>
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
                    <TableCell>
                      {identity.isActive ? (
                        <Badge className="border-emerald-800 bg-emerald-950/50 text-emerald-400" variant="outline">
                          <CheckCircle2 />
                          Active
                        </Badge>
                      ) : (
                        <span className="text-sm text-muted-foreground">Inactive</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground">No agents found.</div>
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
            <div className="p-8 text-center text-sm text-destructive">
              Failed to load principals.
            </div>
          ) : !data ? (
            <div className="divide-y">
              {Array.from({ length: 3 }).map((_, i) => (
                <div className="flex items-center gap-4 px-4 py-3" key={i}>
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-56" />
                  <Skeleton className="h-5 w-14 rounded-full" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
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
          ) : (
            <div className="p-8 text-center text-muted-foreground">No principals found.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function VaultView({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Credential namespace for this account." title="Vault" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="shadow-none border-border/50">
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
    </div>
  );
}

export function AuditView({ data }: { data: DashboardData }) {
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
          ) : (
            <div className="p-8 text-center text-muted-foreground">No audit events found.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function SettingsView({ data }: { data: DashboardData }) {
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

function detailProviderDisplayName(data: ProviderDetail): string {
  return data.provider.display_name || data.provider.name;
}

function detailProviderApiUrl(data: ProviderDetail): string {
  const apiUrl = data.client?.api_url || data.provider.api_url || data.provider.oauth?.base_url || data.provider.name;
  return Array.isArray(apiUrl) ? apiUrl.filter(Boolean).join(", ") : apiUrl;
}

function detailAuthTypeLabel(authType?: string): string {
  return authType === "oauth2" ? "OAuth 2.0" : authType === "api_key" ? "API Key" : authType || "Provider";
}

export function AuthsomeProviderDetailRoute() {
  const searchParams = useSearchParams();
  const provider = searchParams.get("provider") || "";

  if (!provider) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6">
        <Card className="w-full max-w-md border-border/50 shadow-none">
          <CardHeader>
            <CardTitle>Provider not found</CardTitle>
            <CardDescription>Open a provider from the dashboard to view its details.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link className={buttonVariants({ variant: "outline" })} href="/providers">
              Back to providers
            </Link>
          </CardContent>
        </Card>
      </main>
    );
  }

  return <AuthsomeProviderDetail provider={provider} />;
}

export function AuthsomeProviderDetail({ provider }: { provider: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: dashboard, error: dashboardError, mutate: mutateDashboard } = useSWR("authsome-dashboard", fetchDashboard);
  const { data, error, mutate } = useSWR(["authsome-provider-detail", provider], () => fetchProviderDetail(provider));

  useEffect(() => {
    if (isUnauthorized(dashboardError) || isUnauthorized(error)) {
      router.replace(`/login?next=${encodeURIComponent(currentBrowserPath(pathname || providerDetailHref(provider)))}`);
    }
  }, [dashboardError, error, pathname, provider, router]);

  if (isUnauthorized(dashboardError) || isUnauthorized(error)) return <LoadingScreen />;
  if (dashboardError || error) return <ErrorState onRetry={() => { void mutateDashboard(); void mutate(); }} />;
  if (!dashboard || !data) return <LoadingScreen />;

  return (
    <DashboardDetailShell activeView="providers" data={dashboard}>
      <ProviderDetailBody data={data} onRefresh={() => { void mutate(); void mutateDashboard(); }} />
    </DashboardDetailShell>
  );
}

export function ProviderDetailBody({ data, onRefresh }: { data: ProviderDetail; onRefresh: () => void }) {
  const displayName = detailProviderDisplayName(data);
  const initial = (displayName[0] || "?").toUpperCase();
  const description = data.provider.description || data.provider.metadata?.description || "";
  const showsConfiguration = data.provider.auth_type !== "api_key";

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/50 pb-6">
        <div className="flex items-center gap-4">
          <ProviderLogo className="size-12 shrink-0" initial={initial} logo={data.provider.logo || null} />
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold leading-tight text-foreground">{displayName}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {description || detailProviderApiUrl(data)}
            </p>
          </div>
        </div>
        <form action={`/api/auth/providers/${data.provider.name}/connect`} method="post">
          <input name="connection" type="hidden" value="default" />
          <input name="return_url" type="hidden" value={providerDetailHref(data.provider.name)} />
          <Button type="submit">
            <LogIn />
            New connection
          </Button>
        </form>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid gap-5">
          <Card className="border-border/50 shadow-none">
            <CardContent className="grid gap-4 p-5 md:grid-cols-2">
              <KeyValue label="Provider" value={data.provider.name} />
              <KeyValue label="Auth Type" value={detailAuthTypeLabel(data.provider.auth_type)} />
              <KeyValue label="API URL" value={detailProviderApiUrl(data) || "-"} />
              {data.provider.docs_url ? <KeyValue label="Docs" value={data.provider.docs_url} /> : null}
              {data.show_callback_helper && data.callback_url ? (
                <KeyValue label="OAuth Callback URL" value={data.callback_url} />
              ) : null}
            </CardContent>
          </Card>
          <ProviderUsage data={data} />
        </div>
        <div className="grid content-start gap-5">
          {showsConfiguration ? (
            data.account.is_admin ? (
              <ProviderConfigurationForm
                data={data}
                key={data.configuration_fields.map((field) => `${field.name}:${field.default || ""}`).join("|")}
                onRefresh={onRefresh}
              />
            ) : (
              <Card className="border-border/50 shadow-none">
                <CardHeader>
                  <CardTitle>Configuration</CardTitle>
                  <CardDescription>Managed by the admin.</CardDescription>
                </CardHeader>
              </Card>
            )
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ProviderConfigurationForm({ data, onRefresh }: { data: ProviderDetail; onRefresh: () => void }) {
  const initialValues = useMemo(() => {
    const values: Record<string, string> = {};
    for (const field of data.configuration_fields) {
      values[field.name] = field.default || "";
    }
    return values;
  }, [data.configuration_fields]);
  const [values, setValues] = useState(initialValues);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function save() {
    setSaving(true);
    setMessage("");
    try {
      const result = await updateProviderConfiguration(data.provider.name, values);
      setMessage(result.changed ? "Configuration updated." : "No changes to save.");
      onRefresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Configuration could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="border-border/50 shadow-none">
      <CardHeader>
        <CardTitle>Configuration</CardTitle>
        <CardDescription>Provider-level inputs required before users can connect.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {data.configuration_warning ? (
          <div className="rounded-lg border border-amber-800 bg-amber-950/30 px-3 py-2 text-sm text-amber-300">
            {data.configuration_warning}
          </div>
        ) : null}
        {data.configuration_fields.map((field) => (
          <label className="grid gap-2 text-sm" key={field.name}>
            <span className="text-muted-foreground">{field.label}</span>
            <Input
              onChange={(event) => setValues((current) => ({ ...current, [field.name]: event.target.value }))}
              pattern={field.pattern || undefined}
              type="text"
              value={values[field.name] || ""}
            />
            {field.pattern_hint ? <span className="text-xs text-muted-foreground">{field.pattern_hint}</span> : null}
          </label>
        ))}
        {message ? <div className="text-sm text-muted-foreground">{message}</div> : null}
        <Button disabled={saving} onClick={() => void save()} type="button">
          <Save />
          Save
        </Button>
        <RevokeProviderButton data={data} onRefresh={onRefresh} />
      </CardContent>
    </Card>
  );
}

function RevokeProviderButton({ data, onRefresh }: { data: ProviderDetail; onRefresh: () => void }) {
  const [open, setOpen] = useState(false);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");

  async function revoke() {
    setWorking(true);
    setMessage("");
    try {
      await revokeProvider(data.provider.name);
      setOpen(false);
      onRefresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Provider could not be revoked.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <>
      <Button onClick={() => setOpen(true)} type="button" variant="destructive">
        Revoke app
      </Button>
      <Dialog onOpenChange={setOpen} open={open}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revoke app</DialogTitle>
            <DialogDescription>All connections for this provider will be revoked.</DialogDescription>
          </DialogHeader>
          {message ? <div className="text-sm text-destructive">{message}</div> : null}
          <DialogFooter>
            <Button onClick={() => setOpen(false)} type="button" variant="outline">
              Cancel
            </Button>
            <Button disabled={working} onClick={() => void revoke()} type="button" variant="destructive">
              Revoke
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ProviderUsage({ data }: { data: ProviderDetail }) {
  const groups = data.account.is_admin
    ? data.principal_usage
    : [{ principal_id: data.account.principal_id || "current", email: null, connections: data.connections }];

  return (
    <Card className="border-border/50 shadow-none">
      <CardHeader>
        <CardTitle>Connections</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        {groups.length ? (
          groups.map((group) => (
            <div className="grid gap-2" key={group.principal_id}>
              <div className="text-sm font-medium">{group.email || group.principal_id}</div>
              {group.connections.map((connection) => (
                <Link
                  className="flex min-w-0 items-center justify-between gap-3 rounded-lg border bg-muted/30 px-3 py-2 text-sm"
                  href={connectionDetailHref(
                    connection.provider,
                    connection.connection_name,
                    data.account.is_admin ? group.principal_id : null,
                  )}
                  key={`${group.principal_id}:${connection.connection_name}`}
                >
                  <span className="truncate">{connection.connection_name}</span>
                  <StatusBadge status={connection.status} />
                </Link>
              ))}
            </div>
          ))
        ) : (
          <div className="text-sm text-muted-foreground">No connections found.</div>
        )}
      </CardContent>
    </Card>
  );
}

export function AuthsomeConnectionDetailRoute() {
  const searchParams = useSearchParams();
  const provider = searchParams.get("provider") || "";
  const connection = searchParams.get("connection") || "";
  const principal = searchParams.get("principal") || undefined;

  if (!provider || !connection) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6">
        <Card className="w-full max-w-md border-border/50 shadow-none">
          <CardHeader>
            <CardTitle>Connection not found</CardTitle>
            <CardDescription>Open a connection from the dashboard to view its details.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link className={buttonVariants({ variant: "outline" })} href="/connections">
              Back to connections
            </Link>
          </CardContent>
        </Card>
      </main>
    );
  }

  return <AuthsomeConnectionDetail connection={connection} principal={principal} provider={provider} />;
}

export function AuthsomeConnectionDetail({
  connection,
  principal,
  provider,
}: {
  connection: string;
  principal?: string;
  provider: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: dashboard, error: dashboardError, mutate: mutateDashboard } = useSWR("authsome-dashboard", fetchDashboard);
  const { data, error, mutate } = useSWR(["authsome-connection-detail", provider, connection, principal], () =>
    fetchConnectionDetail(provider, connection, principal),
  );

  useEffect(() => {
    if (isUnauthorized(dashboardError) || isUnauthorized(error)) {
      router.replace(`/login?next=${encodeURIComponent(currentBrowserPath(pathname || connectionDetailHref(provider, connection, principal)))}`);
    }
  }, [connection, dashboardError, error, pathname, principal, provider, router]);

  if (isUnauthorized(dashboardError) || isUnauthorized(error)) return <LoadingScreen />;
  if (dashboardError || error) return <ErrorState onRetry={() => { void mutateDashboard(); void mutate(); }} />;
  if (!dashboard || !data) return <LoadingScreen />;

  return (
    <DashboardDetailShell activeView="connections" data={dashboard}>
      <ConnectionDetailBody data={data} onRefresh={() => { void mutate(); void mutateDashboard(); }} principal={principal} />
    </DashboardDetailShell>
  );
}

function SecretValue({ label, value }: { label: string; value: string | null }) {
  const [copied, setCopied] = useState(false);
  if (!value) return null;

  async function copy() {
    await navigator.clipboard.writeText(value || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="grid gap-2">
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      <div className="flex min-w-0 items-start gap-2 rounded-lg border bg-muted p-3">
        <code className="min-w-0 flex-1 break-all text-xs">{value}</code>
        <Button onClick={() => void copy()} size="icon-sm" type="button" variant="ghost">
          {copied ? <Check /> : <Clipboard />}
        </Button>
      </div>
    </div>
  );
}

export function ConnectionDetailBody({
  data,
  onRefresh,
  principal,
}: {
  data: ConnectionDetail;
  onRefresh: () => void;
  principal?: string;
}) {
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/50 pb-6">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{data.provider_display_name}</p>
          <h1 className="mt-0.5 text-2xl font-semibold leading-tight text-foreground">{data.connection_name}</h1>
        </div>
        <ConnectionActions data={data} onRefresh={onRefresh} principal={principal} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
        <Card className="border-border/50 shadow-none">
          <CardContent className="grid gap-4 p-5 md:grid-cols-2">
            <KeyValue label="Status" value={data.status} />
            <KeyValue label="Auth Type" value={data.auth_type} />
            <KeyValue label="Principal ID" value={data.principal_id || "-"} />
            <KeyValue label="Identity" value={data.identity || "-"} />
            <KeyValue label="Scopes" value={data.scopes.join(", ") || "-"} />
            <KeyValue label="Token Type" value={data.token_type || "-"} />
            <KeyValue label="Obtained" value={data.obtained_at || "-"} />
            <KeyValue label="Expires" value={data.expires_at || "-"} />
            <KeyValue label="Base URL" value={data.base_url || "-"} />
            <KeyValue label="API URL" value={data.api_url || "-"} />
          </CardContent>
        </Card>
        <Card className="border-border/50 shadow-none">
          <CardHeader>
            <CardTitle>Secrets</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <SecretValue label="Access Token" value={data.secrets.access_token} />
            <SecretValue label="Refresh Token" value={data.secrets.refresh_token} />
            <SecretValue label="API Key" value={data.secrets.api_key} />
            {Object.entries(data.secrets.credentials).map(([key, value]) => (
              <SecretValue key={key} label={key} value={value} />
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ConnectionActions({
  data,
  onRefresh,
  principal,
}: {
  data: ConnectionDetail;
  onRefresh: () => void;
  principal?: string;
}) {
  const [open, setOpen] = useState(false);
  const [working, setWorking] = useState(false);
  const [globalWorking, setGlobalWorking] = useState(false);
  const [globalMessage, setGlobalMessage] = useState("");

  async function logout() {
    setWorking(true);
    try {
      await logoutConnection(data.provider, data.connection_name, principal);
      setOpen(false);
      onRefresh();
    } finally {
      setWorking(false);
    }
  }

  async function makeGlobal() {
    setGlobalWorking(true);
    setGlobalMessage("");
    try {
      await setGlobalConnection(data.provider, data.connection_name);
      setGlobalMessage("Global connection updated.");
      onRefresh();
    } catch (error) {
      setGlobalMessage(error instanceof Error ? error.message : "Global connection could not be updated.");
    } finally {
      setGlobalWorking(false);
    }
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {data.can_set_default ? (
          <form
            action={`/api/connections/${encodeURIComponent(data.provider)}/${encodeURIComponent(data.connection_name)}/default`}
            method="post"
          >
            <Button size="sm" type="submit" variant="outline">
              Set as default
            </Button>
          </form>
        ) : null}
        {data.can_set_global ? (
          <Button disabled={globalWorking} onClick={() => void makeGlobal()} type="button" variant="outline">
            <Globe2 />
            Make global
          </Button>
        ) : null}
        {globalMessage ? <div className="text-sm text-muted-foreground">{globalMessage}</div> : null}
        <Link className={buttonVariants({ size: "sm", variant: "outline" })} href={providerDetailHref(data.provider)}>
          View provider
        </Link>
        <Button onClick={() => setOpen(true)} size="sm" type="button" variant="destructive">
          <LogOut />
          Logout
        </Button>
      </div>
      <Dialog onOpenChange={setOpen} open={open}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Logout connection</DialogTitle>
            <DialogDescription>This removes the stored credentials for this connection.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setOpen(false)} type="button" variant="outline">
              Cancel
            </Button>
            <Button disabled={working} onClick={() => void logout()} type="button" variant="destructive">
              Logout
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ActiveView({ connectionFilter, data, onRefresh, view }: {
  connectionFilter?: string;
  data: DashboardData;
  onRefresh: () => void;
  view: View;
}) {
  if (view === "providers") return <ProvidersView providers={data.providers} />;
  if (view === "connections") {
    return (
      <ConnectionsView
        connections={data.connections}
        globalConnections={data.globalConnections}
        initialFilter={connectionFilter}
        isAdmin={data.account.isAdmin}
        onRefresh={onRefresh}
      />
    );
  }
  if (view === "agents") return <AgentsView data={data} />;
  if (view === "principals") return <PrincipalsView />;
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
    <SidebarProvider className="h-svh overflow-hidden">
      <AppSidebar activeView={activeView} data={data} />
      <SidebarInset className="min-h-0">
        <Topbar />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid w-full max-w-[86rem] gap-6 p-4 md:p-6">
            <ActiveView
              connectionFilter={connectionFilter}
              data={data}
              onRefresh={() => void mutate()}
              view={activeView}
            />
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
