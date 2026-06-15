"use client";

import { ArrowLeft, Eye, EyeOff, LogIn, Save } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";

import {
  KeyValue,
  ProviderLogo,
  StatusBadge,
  connectionDetailHref,
  providerDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { currentBrowserPath, isUnauthorized } from "@/components/dashboard/dashboard-routing";
import { DashboardDetailShell, ErrorState, LoadingScreen } from "@/components/dashboard/dashboard-shell";
import {
  NamedConnectionDialog,
  NamedConnectionProvider,
} from "@/components/dashboard/provider-views";
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
import {
  ProviderDetail,
  fetchDashboard,
  fetchProviderDetail,
  revokeProvider,
  updateProviderConfiguration,
} from "@/lib/authsome-api";
import { cn } from "@/lib/utils";

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
  const hasDefaultConnection = data.connections.some((connection) => connection.connection_name === "default");
  const dialogData = { displayName, name: data.provider.name };

  return (
    <div className="grid gap-6">
      <Link className={cn(buttonVariants({ size: "sm" }), "w-fit")} href="/providers">
        <ArrowLeft />
        Back to providers
      </Link>
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
        {hasDefaultConnection ? (
          <Button onClick={() => setDialogProvider(dialogData)} type="button">
            <LogIn />
            New connection
          </Button>
        ) : (
          <form action={`/api/auth/providers/${data.provider.name}/connect`} method="post">
            <input name="connection" type="hidden" value="default" />
            <input name="return_url" type="hidden" value="/connections" />
            <Button type="submit">
              <LogIn />
              New connection
            </Button>
          </form>
        )}
      </div>
      <NamedConnectionDialog onOpenChange={setDialogProvider} provider={dialogProvider} />

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
          <ConfigurationFieldInput
            field={field}
            key={field.name}
            onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))}
            value={values[field.name] || ""}
          />
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
    <label className="grid gap-2 text-sm">
      <span className="text-muted-foreground">{field.label}</span>
      <div className="flex items-center gap-2">
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
