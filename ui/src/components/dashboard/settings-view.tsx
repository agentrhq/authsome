"use client";

import { Settings, ShieldCheck, Users, Vault } from "lucide-react";

import { SectionHeader } from "@/components/dashboard/section-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { DashboardData } from "@/lib/authsome-api";

export function SettingsView({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-5">
      <SectionHeader description="Local daemon and account context." title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <SettingsAccountCard data={data} />
        <SettingsVaultCard data={data} />
        <SettingsDaemonCard data={data} />
        <SettingsSecurityCard data={data} />
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
        <SettingsKeyValue label="Last Activity" value={data.lastActivity || "-"} />
        <SettingsKeyValue label="Active Identity" value={data.account.identity || "-"} />
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
