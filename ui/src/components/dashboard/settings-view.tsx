"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ExternalLink, Info, KeyRound, Settings, ShieldCheck, Users, Vault } from "lucide-react";

import { SectionHeader } from "@/components/dashboard/section-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { DashboardData } from "@/lib/authsome-api";

export function GeneralSettingsContent({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Account and vault context for this principal." title="General" />
      <div className="grid gap-4 lg:grid-cols-2">
        <SettingsAccountCard data={data} />
        <SettingsVaultCard data={data} />
      </div>
    </div>
  );
}

export function SecuritySettingsContent({ data }: { data: DashboardData }) {
  const searchParams = useSearchParams();
  const passwordChanged = searchParams.get("password_changed") === "1";
  const passwordError = searchParams.get("password_error");

  return (
    <div className="grid gap-5">
      <SectionHeader description="Credential protection and access controls." title="Security" />
      <div className="grid gap-4 lg:grid-cols-2">
        <SettingsSecurityCard data={data} />
        <SettingsPasswordCard passwordChanged={passwordChanged} passwordError={passwordError} />
      </div>
    </div>
  );
}

export function AboutSettingsContent({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Runtime details and project references." title="About" />
      <div className="grid gap-4 lg:grid-cols-2">
        <SettingsDaemonCard data={data} />
        <SettingsAboutCard />
      </div>
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
      <CardContent className="grid gap-3">
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
      <CardContent className="grid gap-3">
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
      <CardContent className="grid gap-3">
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
          className={buttonVariants({ variant: "outline" })}
          href="https://authsome.ai/docs"
          rel="noreferrer"
          target="_blank"
        >
          Docs
          <ExternalLink />
        </Link>
        <Link
          className={buttonVariants({ variant: "outline" })}
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
      <CardContent className="grid gap-3">
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
        <form action="/api/auth/password" className="grid gap-3" method="post">
          <input name="next" type="hidden" value="/settings/security?password_changed=1" />
          {passwordChanged ? (
            <div className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300" role="status">
              Password updated.
            </div>
          ) : null}
          {passwordError ? (
            <div className="rounded-lg border border-destructive/60 bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
              {passwordError}
            </div>
          ) : null}
          <label className="grid gap-1.5 text-sm">
            <span className="text-muted-foreground">Current password</span>
            <Input autoComplete="current-password" name="current_password" required type="password" />
          </label>
          <label className="grid gap-1.5 text-sm">
            <span className="text-muted-foreground">New password</span>
            <Input autoComplete="new-password" minLength={8} name="new_password" required type="password" />
          </label>
          <Button className="w-fit" type="submit">
            <KeyRound />
            Change password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export function SettingsKeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1.5">
      <div className="text-sm text-muted-foreground">{label}</div>
      <Tooltip>
        <TooltipTrigger render={<div className="truncate rounded-md border bg-muted/50 px-3 py-2 font-mono text-sm" />}>
          {value}
        </TooltipTrigger>
        <TooltipContent>{value}</TooltipContent>
      </Tooltip>
    </div>
  );
}
