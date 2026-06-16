"use client";

import { Check, Clipboard, Clock, Eye, EyeOff, Globe2, KeyRound, Link2, LogOut, Server, Shield } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import useSWR from "swr";

import {
  ProviderLogo,
  StatusBadge,
  connectionDetailHref,
  providerDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { currentBrowserPath, isUnauthorized } from "@/components/dashboard/dashboard-routing";
import { DashboardDetailShell, ErrorState, LoadingScreen } from "@/components/dashboard/dashboard-shell";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { H3 } from "@/components/ui/typography";
import {
  ConnectionDetail,
  DashboardData,
  fetchConnectionDetail,
  fetchDashboard,
  logoutConnection,
  setGlobalConnection,
  unsetGlobalConnection,
} from "@/lib/authsome-api";
import { cn } from "@/lib/utils";

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
      <ConnectionDetailBody data={data} onRefresh={() => { void mutate(); void mutateDashboard(); }} principal={principal} providers={dashboard.providers} />
    </DashboardDetailShell>
  );
}

export function ConnectionDetailBody({
  data,
  onRefresh,
  principal,
  providers,
}: {
  data: ConnectionDetail;
  onRefresh: () => void;
  principal?: string;
  providers?: DashboardData["providers"];
}) {
  const provider = providers?.find((p) => p.name === data.provider);
  const hasSecrets = data.secrets.access_token || data.secrets.refresh_token || data.secrets.api_key || Object.keys(data.secrets.credentials).length > 0;
  const hasEndpoints = data.base_url || data.api_url;

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/50 pb-4">
        <div className="flex items-center gap-3 min-w-0">
          {provider ? (
            <ProviderLogo className="size-10 shrink-0" initial={provider.logoInitial} logo={provider.logo} />
          ) : null}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Link className="text-sm text-muted-foreground hover:text-foreground hover:underline" href={providerDetailHref(data.provider)}>
                {data.provider_display_name}
              </Link>
              {data.is_global ? (
                <Badge className="border-primary/30 bg-primary/10 text-primary" variant="outline">
                  <Globe2 className="size-3" />
                  Global
                </Badge>
              ) : null}
            </div>
            <H3 className="mt-0.5 leading-tight">{data.connection_name}</H3>
          </div>
        </div>
        <ConnectionActions data={data} onRefresh={onRefresh} principal={principal} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="grid gap-4">
          <Card className="border-border/50 shadow-none">
            <CardHeader className="pb-0">
              <CardTitle className="flex items-center gap-2">
                <Shield className="size-4 text-muted-foreground" />
                Identity &amp; Access
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 pt-4 md:grid-cols-2">
              <DetailField label="Status">
                <StatusBadge status={data.status} />
              </DetailField>
              <DetailField label="Auth Type">
                <span className="text-sm">{authTypeLabel(data.auth_type)}</span>
              </DetailField>
              <DetailField label="Principal ID">
                <code className="text-xs font-mono text-muted-foreground">{data.principal_id || "-"}</code>
              </DetailField>
              <DetailField label="Agent">
                <span className="text-sm">{data.identity || "-"}</span>
              </DetailField>
              {data.scopes.length > 0 ? (
                <div className="md:col-span-2">
                  <DetailField label="Scopes">
                    <div className="flex flex-wrap gap-1.5">
                      {data.scopes.map((scope) => (
                        <Badge key={scope} variant="outline">{scope}</Badge>
                      ))}
                    </div>
                  </DetailField>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="border-border/50 shadow-none">
            <CardHeader className="pb-0">
              <CardTitle className="flex items-center gap-2">
                <Clock className="size-4 text-muted-foreground" />
                Token
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 pt-4 md:grid-cols-2">
              <DetailField label="Token Type">
                <span className="text-sm">{data.token_type || "-"}</span>
              </DetailField>
              <DetailField label="Obtained">
                <span className="text-sm">{formatTimestamp(data.obtained_at)}</span>
              </DetailField>
              <DetailField label="Expires">
                <span className="text-sm">{formatTimestamp(data.expires_at)}</span>
              </DetailField>
            </CardContent>
          </Card>

          {hasEndpoints ? (
            <Card className="border-border/50 shadow-none">
              <CardHeader className="pb-0">
                <CardTitle className="flex items-center gap-2">
                  <Server className="size-4 text-muted-foreground" />
                  Endpoints
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 pt-4">
                {data.base_url ? (
                  <DetailField label="Base URL">
                    <code className="text-xs font-mono break-all">{data.base_url}</code>
                  </DetailField>
                ) : null}
                {data.api_url ? (
                  <DetailField label="API URL">
                    <code className="text-xs font-mono break-all">{data.api_url}</code>
                  </DetailField>
                ) : null}
              </CardContent>
            </Card>
          ) : null}
        </div>

        {hasSecrets ? (
          <Card className="border-border/50 shadow-none h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <KeyRound className="size-4 text-muted-foreground" />
                Secrets
              </CardTitle>
              <CardDescription>Encrypted at rest in the vault.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <SecretValue label="Access Token" value={data.secrets.access_token} />
              <SecretValue label="Refresh Token" value={data.secrets.refresh_token} />
              <SecretValue label="API Key" value={data.secrets.api_key} />
              {Object.entries(data.secrets.credentials).map(([key, value]) => (
                <SecretValue key={key} label={key} value={value} />
              ))}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function DetailField({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="grid gap-1">
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div>{children}</div>
    </div>
  );
}

function authTypeLabel(authType: string): string {
  return authType === "oauth2" ? "OAuth 2.0" : authType === "api_key" ? "API Key" : authType || "-";
}

function formatTimestamp(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function redactedValue(value: string): string {
  return value.length <= 8 ? "********" : `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function SecretValue({ label, value }: { label: string; value: string | null }) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(false);
  if (!value) return null;

  async function copy() {
    await navigator.clipboard.writeText(value || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="grid gap-1.5">
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="flex min-w-0 items-start gap-1.5 rounded-md border bg-muted/50 p-2.5">
        <code className="min-w-0 flex-1 break-all pt-0.5 text-xs">{revealed ? value : redactedValue(value)}</code>
        <Button
          aria-label={revealed ? "Hide secret" : "Reveal secret"}
          onClick={() => setRevealed((current) => !current)}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          {revealed ? <EyeOff /> : <Eye />}
        </Button>
        <Button
          aria-label="Copy secret"
          onClick={() => void copy()}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          {copied ? <Check className="text-emerald-600 dark:text-emerald-400" /> : <Clipboard />}
        </Button>
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
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [working, setWorking] = useState(false);
  const [globalWorking, setGlobalWorking] = useState(false);
  const [globalMessage, setGlobalMessage] = useState<{ text: string; tone: "error" | "success" } | null>(null);

  async function logout() {
    setWorking(true);
    try {
      await logoutConnection(data.provider, data.connection_name, principal);
      setOpen(false);
      onRefresh();
      router.replace("/connections");
    } finally {
      setWorking(false);
    }
  }

  async function toggleGlobal() {
    setGlobalWorking(true);
    setGlobalMessage(null);
    try {
      if (data.is_global) {
        await unsetGlobalConnection(data.provider);
        setGlobalMessage({ text: "Global connection removed.", tone: "success" });
      } else {
        await setGlobalConnection(data.provider, data.connection_name);
        setGlobalMessage({ text: "Global connection updated.", tone: "success" });
      }
      onRefresh();
    } catch (error) {
      setGlobalMessage({
        text: error instanceof Error ? error.message : "Global connection could not be updated.",
        tone: "error",
      });
    } finally {
      setGlobalWorking(false);
    }
  }

  return (
    <>
      <div className="flex flex-col items-start gap-2 sm:items-end">
        <div className="flex flex-wrap items-center gap-2">
          {data.can_set_default ? (
            <form
              action={`/api/connections/${encodeURIComponent(data.provider)}/${encodeURIComponent(data.connection_name)}/default`}
              method="post"
            >
              <Button size="sm" type="submit" variant="outline">
                <Link2 />
                Set as default
              </Button>
            </form>
          ) : null}
          {data.can_set_global ? (
            <Button disabled={globalWorking} onClick={() => void toggleGlobal()} size="sm" type="button" variant="outline">
              <Globe2 />
              {data.is_global ? "Unset global" : "Make global"}
            </Button>
          ) : null}
          <Link className={buttonVariants({ size: "sm", variant: "outline" })} href={providerDetailHref(data.provider)}>
            View provider
          </Link>
          <Button onClick={() => setOpen(true)} size="sm" type="button" variant="destructive">
            <LogOut />
            Logout
          </Button>
        </div>
        {globalMessage ? (
          <div
            aria-live="polite"
            className={cn(
              "text-sm",
              globalMessage.tone === "success" ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"
            )}
          >
            {globalMessage.text}
          </div>
        ) : null}
      </div>
      <Dialog onOpenChange={setOpen} open={open}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Logout connection</DialogTitle>
            <DialogDescription>
              This removes the stored credentials for &ldquo;{data.connection_name}&rdquo; on {data.provider_display_name}.
            </DialogDescription>
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
