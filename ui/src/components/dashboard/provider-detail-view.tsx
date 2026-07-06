"use client";

import { Check, Clipboard, ExternalLink, Eye, EyeOff, Link2, LogIn, Save, Settings, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import useSWR from "swr";

import {
  ProviderLogo,
  StatusBadge,
  connectionDetailHref,
  providerDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { PageEmptyState } from "@/components/dashboard/page-state";
import { currentBrowserPath, isUnauthorized } from "@/components/dashboard/dashboard-routing";
import { DashboardDetailShell, ErrorState, LoadingScreen } from "@/components/dashboard/dashboard-shell";
import {
  NamedConnectionDialog,
  NamedConnectionProvider,
} from "@/components/dashboard/provider-views";
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
import { Input } from "@/components/ui/input";
import { H3 } from "@/components/ui/typography";
import {
  ProviderDetail,
  fetchDashboard,
  fetchProviderDetail,
  revokeProvider,
  updateProviderConfiguration,
} from "@/lib/authsome-api";

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
  const [dialogProvider, setDialogProvider] = useState<NamedConnectionProvider | null>(null);
  const dialogData = { displayName, name: data.provider.name };
  const hasConnections = data.connections.length > 0 || data.principal_usage.some((g) => g.connections.length > 0);
  const providerStatus = hasConnections ? "connected" : "available";

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border/50 pb-4">
        <div className="flex items-center gap-3 min-w-0">
          <ProviderLogo className="size-10 shrink-0" initial={initial} logo={data.provider.logo || null} />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <H3 className="leading-tight">{displayName}</H3>
              <StatusBadge status={providerStatus} />
            </div>
            <span className="mt-0.5 text-sm text-muted-foreground">
              {description || detailProviderApiUrl(data)}
            </span>
          </div>
        </div>
        <Button onClick={() => setDialogProvider(dialogData)} size="sm" type="button">
          <LogIn />
          New connection
        </Button>
      </div>
      <NamedConnectionDialog onOpenChange={setDialogProvider} provider={dialogProvider} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid gap-4">
          <Card className="border-border/50 shadow-none">
            <CardHeader className="pb-0">
              <CardTitle className="flex items-center gap-2">
                <Settings className="size-4 text-muted-foreground" />
                Provider Details
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 pt-4 md:grid-cols-2">
              <DetailField label="Provider ID">
                <code className="text-xs font-mono text-muted-foreground">{data.provider.name}</code>
              </DetailField>
              <DetailField label="Auth Type">
                <span className="text-sm">{detailAuthTypeLabel(data.provider.auth_type)}</span>
              </DetailField>
              <DetailField label="API URL">
                <code className="text-xs font-mono break-all">{detailProviderApiUrl(data) || "-"}</code>
              </DetailField>
              {data.provider.docs_url ? (
                <DetailField label="Documentation">
                  <a
                    className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                    href={data.provider.docs_url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {data.provider.docs_url.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                    <ExternalLink className="size-3 shrink-0" />
                  </a>
                </DetailField>
              ) : null}
              {data.provider.auth_type !== "api_key" && data.show_callback_helper && data.callback_url ? (
                <div className="md:col-span-2">
                  <CopyableField label="OAuth Callback URL" value={data.callback_url} />
                </div>
              ) : null}
            </CardContent>
          </Card>
          <ProviderUsage data={data} />
        </div>
        <div className="grid content-start gap-4">
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
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="size-4 text-muted-foreground" />
                    Configuration
                  </CardTitle>
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

function DetailField({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="grid gap-1">
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div>{children}</div>
    </div>
  );
}

function CopyableField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="grid gap-1">
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="flex min-w-0 items-center gap-1.5 rounded-md border bg-muted/50 p-2.5">
        <code className="min-w-0 flex-1 break-all text-xs">{value}</code>
        <Button
          aria-label={`Copy ${label}`}
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
  const [message, setMessage] = useState<{ text: string; tone: "error" | "success" | "muted" } | null>(null);

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      const result = await updateProviderConfiguration(data.provider.name, values);
      setMessage({
        text: result.changed ? "Configuration updated." : "No changes to save.",
        tone: result.changed ? "success" : "muted",
      });
      onRefresh();
    } catch (error) {
      setMessage({
        text: error instanceof Error ? error.message : "Configuration could not be saved.",
        tone: "error",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Card className="border-border/50 shadow-none">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="size-4 text-muted-foreground" />
            Configuration
          </CardTitle>
          <CardDescription>Provider-level inputs required before users can connect.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {data.configuration_warning ? (
            <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300" role="alert">
              {data.configuration_warning}
            </div>
          ) : null}
          {data.configuration_fields.map((field) => (
            <ConfigurationFieldInput
              field={field}
              key={field.name}
              onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))}
              value={values[field.name] || ""}
            />
          ))}
          {message ? (
            <div className={
              message.tone === "success" ? "text-sm text-emerald-700 dark:text-emerald-400"
              : message.tone === "error" ? "text-sm text-destructive"
              : "text-sm text-muted-foreground"
            }>
              {message.text}
            </div>
          ) : null}
          <Button disabled={saving} onClick={() => void save()} type="button">
            <Save />
            Save
          </Button>
        </CardContent>
      </Card>
      <RevokeProviderButton data={data} onRefresh={onRefresh} />
    </>
  );
}

function RevokeProviderButton({ data, onRefresh }: { data: ProviderDetail; onRefresh: () => void }) {
  const displayName = detailProviderDisplayName(data);
  const connectionCount = data.connections.length;
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
      <Card className="border-destructive/30 shadow-none">
        <CardContent className="flex items-center justify-between gap-4 py-3">
          <div className="min-w-0">
            <div className="text-sm font-medium">Revoke app</div>
            <div className="text-xs text-muted-foreground">Remove all credentials for this provider.</div>
          </div>
          <Button onClick={() => setOpen(true)} size="sm" type="button" variant="destructive">
            Revoke
          </Button>
        </CardContent>
      </Card>
      <Dialog onOpenChange={setOpen} open={open}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revoke {displayName}</DialogTitle>
            <DialogDescription>
              {connectionCount
                ? `This will revoke all ${connectionCount} connection${connectionCount === 1 ? "" : "s"} for ${displayName}. Stored credentials will be removed.`
                : `This will revoke the app registration for ${displayName}.`}
            </DialogDescription>
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
  const totalConnections = groups.reduce((sum, group) => sum + group.connections.length, 0);

  return (
    <Card className="border-border/50 shadow-none">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Link2 className="size-4 text-muted-foreground" />
            Connections
          </CardTitle>
          {totalConnections > 0 ? (
            <Badge variant="outline">{totalConnections}</Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="grid gap-4">
        {groups.length && totalConnections > 0 ? (
          groups.filter((g) => g.connections.length > 0).map((group) => (
            <div className="grid gap-2" key={group.principal_id}>
              {data.account.is_admin ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <UserRound className="size-3.5" />
                  <span className="font-medium">{group.email || group.principal_id}</span>
                </div>
              ) : null}
              {group.connections.map((connection) => (
                <Link
                  className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-border/50 bg-muted/30 px-3 py-2.5 text-sm transition-colors hover:border-primary/50 hover:bg-muted/50"
                  href={connectionDetailHref(
                    connection.provider,
                    connection.connection_name,
                    data.account.is_admin ? group.principal_id : null,
                  )}
                  key={`${group.principal_id}:${connection.connection_name}`}
                >
                  <div className="min-w-0">
                    <div className="truncate font-medium">{connection.connection_name}</div>
                    {connection.account_label ? (
                      <div className="truncate text-xs text-muted-foreground">{connection.account_label}</div>
                    ) : null}
                  </div>
                  <StatusBadge status={connection.status} />
                </Link>
              ))}
            </div>
          ))
        ) : (
          <PageEmptyState
            description="Use the button above to create a connection."
            title="No connections yet"
          />
        )}
      </CardContent>
    </Card>
  );
}

function ConfigurationFieldInput({
  field,
  onChange,
  value,
}: {
  field: ProviderDetail["configuration_fields"][number];
  onChange: (value: string) => void;
  value: string;
}) {
  const [revealed, setRevealed] = useState(false);
  const isSecret = field.secret;

  return (
    <label className="grid gap-1.5 text-sm">
      <span className="text-muted-foreground">{field.label}</span>
      <div className="flex items-center gap-1.5">
        <Input
          className="min-w-0 flex-1"
          onChange={(event) => onChange(event.target.value)}
          pattern={field.pattern || undefined}
          type={isSecret && !revealed ? "password" : "text"}
          value={value}
        />
        {isSecret ? (
          <Button
            aria-label={revealed ? "Hide secret" : "Reveal secret"}
            onClick={() => setRevealed((current) => !current)}
            size="icon"
            type="button"
            variant="outline"
          >
            {revealed ? <EyeOff /> : <Eye />}
          </Button>
        ) : null}
      </div>
      {field.pattern_hint ? <span className="text-xs text-muted-foreground">{field.pattern_hint}</span> : null}
    </label>
  );
}
