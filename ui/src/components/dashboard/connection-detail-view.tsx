"use client";

import { ArrowLeft, Check, Clipboard, Eye, EyeOff, Globe2, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR from "swr";

import {
  KeyValue,
  connectionDetailHref,
  providerDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { currentBrowserPath, isUnauthorized } from "@/components/dashboard/dashboard-routing";
import { DashboardDetailShell, ErrorState, LoadingScreen } from "@/components/dashboard/dashboard-shell";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ConnectionDetail,
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
      <ConnectionDetailBody data={data} onRefresh={() => { void mutate(); void mutateDashboard(); }} principal={principal} />
    </DashboardDetailShell>
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
      <Link className={cn(buttonVariants({ size: "sm", variant: "outline" }), "w-fit")} href="/connections">
        <ArrowLeft />
        Back to connections
      </Link>
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
            <KeyValue label="Agent" value={data.identity || "-"} />
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
    <div className="grid gap-2">
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      <div className="flex min-w-0 items-start gap-2 rounded-lg border bg-muted p-3">
        <code className="min-w-0 flex-1 break-all text-xs">{revealed ? value : redactedValue(value)}</code>
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
          disabled={!revealed}
          onClick={() => void copy()}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          {copied ? <Check /> : <Clipboard />}
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
      <div className="flex flex-col items-start gap-1 sm:items-end">
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
            <Button disabled={globalWorking} onClick={() => void toggleGlobal()} type="button" variant="outline">
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
        <div
          aria-live="polite"
          className={cn(
            "min-h-5 text-sm",
            globalMessage?.tone === "success" ? "text-emerald-400" : "text-destructive"
          )}
        >
          {globalMessage?.text}
        </div>
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
