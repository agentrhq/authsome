"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ExternalLink, Info, KeyRound, Settings, ShieldCheck, Users, Vault } from "lucide-react";

import { SectionHeader } from "@/components/dashboard/section-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { DashboardData } from "@/lib/authsome-api";

const SETTINGS_TABS = new Set(["account", "about", "security"]);

export function SettingsView({ data }: { data: DashboardData }) {
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab") || "account";
  const defaultTab = SETTINGS_TABS.has(requestedTab) ? requestedTab : "account";
  const passwordChanged = searchParams.get("password_changed") === "1";
  const passwordError = searchParams.get("password_error");

  return (
    <div className="grid gap-5">
      <SectionHeader description="Account, runtime, and security context." title="Settings" />
      <Tabs className="gap-5" defaultValue={defaultTab}>
        <TabsList className="grid h-auto w-full grid-cols-3 md:w-fit">
          <TabsTrigger value="account">General</TabsTrigger>
          <TabsTrigger value="about">About</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
        </TabsList>
        <TabsContent className="grid gap-4 lg:grid-cols-2" value="account">
          <SettingsAccountCard data={data} />
          <SettingsVaultCard data={data} />
        </TabsContent>
        <TabsContent className="grid gap-4 lg:grid-cols-2" value="about">
          <SettingsDaemonCard data={data} />
          <SettingsAboutCard />
        </TabsContent>
        <TabsContent className="grid gap-4 lg:grid-cols-2" value="security">
          <SettingsSecurityCard data={data} />
          <SettingsPasswordCard passwordChanged={passwordChanged} passwordError={passwordError} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SettingsAccountCard({ data }: { data: DashboardData }) {
  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="size-4 text-muted-foreground" />
          Account
        </CardTitle>
        <CardDescription>Principal and dashboard session context.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <SettingsKeyValue label="Email" value={data.account.email || "-"} />
        <SettingsKeyValue label="Role" value={data.account.roleLabel || "-"} />
        <SettingsKeyValue label="Principal ID" value={data.account.principalId || "-"} />
      </CardContent>
    </Card>
  );
}

function SettingsVaultCard({ data }: { data: DashboardData }) {
  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Vault className="size-4 text-muted-foreground" />
          Vault
        </CardTitle>
        <CardDescription>Credential namespace used by this account.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <SettingsKeyValue label="Handle" value={data.vault.handle || "-"} />
        <SettingsKeyValue label="Vault ID" value={data.vault.vaultId || "-"} />
        <SettingsKeyValue label="Default Vault" value={data.vault.isDefault ? "Yes" : "No"} />
      </CardContent>
    </Card>
  );
}

function SettingsDaemonCard({ data }: { data: DashboardData }) {
  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="size-4 text-muted-foreground" />
          Daemon
        </CardTitle>
        <CardDescription>Runtime and local service details.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <SettingsKeyValue label="Version" value={data.version} />
        <SettingsKeyValue label="Latest Token Expiry" value={data.latestTokenExpiry || "-"} />
      </CardContent>
    </Card>
  );
}

function SettingsAboutCard() {
  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Info className="size-4 text-muted-foreground" />
          About
        </CardTitle>
        <CardDescription>Project resources and release references.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Link
          className={buttonVariants({ size: "sm", variant: "outline" })}
          href="https://authsome.ai/docs"
          rel="noreferrer"
          target="_blank"
        >
          Docs
          <ExternalLink />
        </Link>
        <Link
          className={buttonVariants({ size: "sm", variant: "outline" })}
          href="https://github.com/agentrhq/authsome/releases"
          rel="noreferrer"
          target="_blank"
        >
          Releases
          <ExternalLink />
        </Link>
      </CardContent>
    </Card>
  );
}

function SettingsSecurityCard({ data }: { data: DashboardData }) {
  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-muted-foreground" />
          Security
        </CardTitle>
        <CardDescription>Credential protection and administrative visibility.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <SettingsKeyValue label="Encryption" value={data.account.principalId ? "AES-256-GCM" : "-"} />
        <SettingsKeyValue label="Audit Access" value={data.audit.canView ? "Available" : "Unavailable"} />
        <SettingsKeyValue label="Audit Events" value={String(data.audit.total)} />
      </CardContent>
    </Card>
  );
}

function SettingsPasswordCard({
  passwordChanged,
  passwordError,
}: {
  passwordChanged: boolean;
  passwordError: string | null;
}) {
  return (
    <Card className="shadow-none border-border/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-muted-foreground" />
          Password
        </CardTitle>
        <CardDescription>Hosted account credential.</CardDescription>
      </CardHeader>
      <CardContent>
        <form action="/api/auth/password" className="grid gap-4" method="post">
          <input name="next" type="hidden" value="/settings?tab=security" />
          {passwordChanged ? (
            <div className="rounded-lg border border-emerald-800 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-300">
              Password updated.
            </div>
          ) : null}
          {passwordError ? (
            <div className="rounded-lg border border-destructive/60 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {passwordError}
            </div>
          ) : null}
          <label className="grid gap-1 text-sm font-medium">
            Current password
            <Input autoComplete="current-password" name="current_password" required type="password" />
          </label>
          <label className="grid gap-1 text-sm font-medium">
            New password
            <Input autoComplete="new-password" minLength={8} name="new_password" required type="password" />
          </label>
          <Button className="w-fit" size="sm" type="submit">
            <KeyRound />
            Change password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function SettingsKeyValue({ label, value }: { label: string; value: string }) {
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
