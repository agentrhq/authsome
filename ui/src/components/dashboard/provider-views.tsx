"use client";

import { Bot, Boxes, Globe2, GlobeIcon, KeyRound, Link2, LogIn, Monitor, Pencil, Plus, Shield, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";

import { CustomProviderDialog } from "@/components/dashboard/custom-provider-form";
import {
  INTERACTIVE_CARD_CLASS,
  ProviderLogo,
  SearchInput,
  StatusBadge,
  providerDetailHref,
} from "@/components/dashboard/dashboard-primitives";
import { PageEmptyState } from "@/components/dashboard/page-state";
import { SectionHeader } from "@/components/dashboard/section-header";
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
import { ProviderView, deleteCustomProvider } from "@/lib/authsome-api";
import { cn } from "@/lib/utils";

export function ProviderSummary({ provider }: { provider: ProviderView }) {
  return (
    <Link
      className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 px-4 py-3 transition-colors hover:border-primary/50 hover:bg-muted/50"
      href={providerDetailHref(provider.name)}
    >
      <div className="flex items-center gap-3">
        <ProviderLogo className="size-8" initial={provider.logoInitial} logo={provider.logo} />
        <div>
          <div className="text-sm font-medium">{provider.displayName}</div>
          <div className="text-xs text-muted-foreground">{provider.authTypeLabel}</div>
        </div>
      </div>
      <StatusBadge status={provider.status} />
    </Link>
  );
}

type AuthTypeFilter = "all" | "oauth2" | "api_key";
type ProviderTypeFilter = "all" | "app" | "llm" | "mcp" | "browser";
type StatusFilter = "all" | "connected" | "available";

const AUTH_TYPE_FILTERS: { label: string; value: AuthTypeFilter }[] = [
  { label: "All Types", value: "all" },
  { label: "OAuth", value: "oauth2" },
  { label: "API Key", value: "api_key" },
];

const PROVIDER_TYPE_FILTERS: { icon: typeof Bot; label: string; value: ProviderTypeFilter }[] = [
  { icon: Boxes, label: "All", value: "all" },
  { icon: Monitor, label: "App", value: "app" },
  { icon: Bot, label: "LLM", value: "llm" },
  { icon: Link2, label: "MCP", value: "mcp" },
  { icon: GlobeIcon, label: "Browser", value: "browser" },
];

const STATUS_FILTERS: { label: string; value: StatusFilter }[] = [
  { label: "All", value: "all" },
  { label: "Connected", value: "connected" },
  { label: "Available", value: "available" },
];

export function ProvidersView({
  isAdmin = false,
  onRefresh,
  providers,
}: {
  isAdmin?: boolean;
  onRefresh?: () => void;
  providers: ProviderView[];
}) {
  const [query, setQuery] = useState("");
  const [authTypeFilter, setAuthTypeFilter] = useState<AuthTypeFilter>("all");
  const [providerTypeFilter, setProviderTypeFilter] = useState<ProviderTypeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [dialogProvider, setDialogProvider] = useState<NamedConnectionProvider | null>(null);
  const [formState, setFormState] = useState<{ mode: "create" | "edit"; provider?: ProviderView } | null>(null);
  const [deleteProvider, setDeleteProvider] = useState<ProviderView | null>(null);

  const hasProviderTypes = useMemo(
    () => providers.some((p) => p.providerType),
    [providers],
  );

  const filteredProviders = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const matches = providers.filter((provider) => {
      if (normalized && !`${provider.displayName} ${provider.name} ${provider.authTypeLabel} ${provider.description}`
        .toLowerCase()
        .includes(normalized)) {
        return false;
      }
      if (authTypeFilter !== "all" && provider.authType !== authTypeFilter) return false;
      if (providerTypeFilter !== "all" && provider.providerType !== providerTypeFilter) return false;
      if (statusFilter === "connected" && provider.status === "available") return false;
      if (statusFilter === "available" && provider.status !== "available") return false;
      return true;
    });

    return [...matches].sort((a, b) =>
      providerSortRank(a) - providerSortRank(b)
      || a.displayName.localeCompare(b.displayName),
    );
  }, [providers, query, authTypeFilter, providerTypeFilter, statusFilter]);

  const hasActiveFilters = authTypeFilter !== "all" || providerTypeFilter !== "all" || statusFilter !== "all" || query.trim().length > 0;

  return (
    <div className="grid gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeader description="Configure providers and start browser login flows." title="Providers" />
        {isAdmin ? (
          <Button onClick={() => setFormState({ mode: "create" })} type="button">
            <Plus />
            New provider
          </Button>
        ) : null}
      </div>
      <div className="grid gap-3">
        <SearchInput onChange={setQuery} placeholder="Search providers..." value={query} />
        <div className="flex flex-wrap items-center gap-2">
          {AUTH_TYPE_FILTERS.map((filter) => (
            <button
              className={cn(
                "inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors",
                authTypeFilter === filter.value
                  ? "border-primary/50 bg-primary/10 text-primary"
                  : "border-border/50 bg-background text-muted-foreground hover:border-border hover:text-foreground",
              )}
              key={filter.value}
              onClick={() => setAuthTypeFilter(filter.value)}
              type="button"
            >
              {filter.value === "oauth2" ? <Shield className="size-3" /> : null}
              {filter.value === "api_key" ? <KeyRound className="size-3" /> : null}
              {filter.label}
            </button>
          ))}
          {hasProviderTypes ? (
            <>
              <span className="mx-1 h-4 w-px bg-border/50" />
              {PROVIDER_TYPE_FILTERS.map((filter) => {
                const Icon = filter.value !== "all" ? filter.icon : null;
                return (
                  <button
                    className={cn(
                      "inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors",
                      providerTypeFilter === filter.value
                        ? "border-primary/50 bg-primary/10 text-primary"
                        : "border-border/50 bg-background text-muted-foreground hover:border-border hover:text-foreground",
                    )}
                    key={filter.value}
                    onClick={() => setProviderTypeFilter(filter.value)}
                    type="button"
                  >
                    {Icon ? <Icon className="size-3" /> : null}
                    {filter.label}
                  </button>
                );
              })}
            </>
          ) : null}
          <span className="mx-1 h-4 w-px bg-border/50" />
          {STATUS_FILTERS.map((filter) => (
            <button
              className={cn(
                "inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors",
                statusFilter === filter.value
                  ? "border-primary/50 bg-primary/10 text-primary"
                  : "border-border/50 bg-background text-muted-foreground hover:border-border hover:text-foreground",
              )}
              key={filter.value}
              onClick={() => setStatusFilter(filter.value)}
              type="button"
            >
              {filter.label}
            </button>
          ))}
          {hasActiveFilters ? (
            <>
              <span className="mx-1 h-4 w-px bg-border/50" />
              <span className="text-xs text-muted-foreground">
                {filteredProviders.length} of {providers.length}
              </span>
            </>
          ) : null}
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filteredProviders.map((provider) => (
          <ProviderCard
            isAdmin={isAdmin}
            key={provider.name}
            onDelete={() => setDeleteProvider(provider)}
            onEdit={() => setFormState({ mode: "edit", provider })}
            onNamedLogin={() => setDialogProvider(provider)}
            provider={provider}
          />
        ))}
      </div>
      {!filteredProviders.length ? (
        hasActiveFilters ? (
          <PageEmptyState
            actionLabel="Clear filters"
            onAction={() => { setQuery(""); setAuthTypeFilter("all"); setProviderTypeFilter("all"); setStatusFilter("all"); }}
            title="No matching providers"
          />
        ) : (
          <PageEmptyState title="No providers available" />
        )
      ) : null}
      <NamedConnectionDialog onOpenChange={setDialogProvider} provider={dialogProvider} />
      <CustomProviderDialog
        key={`${formState?.mode || "create"}:${formState?.provider?.name || "new"}`}
        mode={formState?.mode || "create"}
        onOpenChange={(open) => {
          if (!open) setFormState(null);
        }}
        onSaved={() => onRefresh?.()}
        open={Boolean(formState)}
        provider={formState?.provider?.definition || null}
      />
      <DeleteCustomProviderDialog
        onDeleted={() => onRefresh?.()}
        onOpenChange={(open) => {
          if (!open) setDeleteProvider(null);
        }}
        provider={deleteProvider}
      />
    </div>
  );
}

function providerSortRank(provider: ProviderView): number {
  return provider.status === "available" ? 1 : 0;
}

function ProviderCard({
  isAdmin,
  onDelete,
  onEdit,
  onNamedLogin,
  provider,
}: {
  isAdmin: boolean;
  onDelete: () => void;
  onEdit: () => void;
  onNamedLogin: () => void;
  provider: ProviderView;
}) {
  const router = useRouter();
  const canManage = isAdmin && provider.source === "custom";

  return (
    <Card
      className={cn("flex h-full flex-col", INTERACTIVE_CARD_CLASS)}
      onClick={() => router.push(providerDetailHref(provider.name))}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-3 min-w-0">
            <ProviderLogo className="size-11 shrink-0" initial={provider.logoInitial} logo={provider.logo} />
            <div className="min-w-0">
              <CardTitle className="truncate text-base leading-tight">{provider.displayName}</CardTitle>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <Badge variant="outline" className="gap-1">
                  {provider.authType === "oauth2" ? <Shield className="size-3" /> : <KeyRound className="size-3" />}
                  {provider.authTypeLabel}
                </Badge>
                {provider.globalConnectionCount ? (
                  <Badge className="gap-1 border-primary/30 bg-primary/10 text-primary" variant="outline">
                    <Globe2 className="size-3" />
                    Global
                  </Badge>
                ) : null}
                {provider.source === "custom" ? (
                  <Badge variant="outline">Custom</Badge>
                ) : null}
              </div>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {canManage ? (
              <>
                <Button
                  aria-label={`Edit ${provider.displayName}`}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onEdit();
                  }}
                  size="icon-sm"
                  type="button"
                  variant="outline"
                >
                  <Pencil />
                </Button>
                <Button
                  aria-label={`Delete ${provider.displayName}`}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onDelete();
                  }}
                  size="icon-sm"
                  type="button"
                  variant="outline"
                >
                  <Trash2 />
                </Button>
              </>
            ) : null}
            <StatusBadge status={provider.status} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3 pt-0">
        <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
          {provider.description || "Connect to store and inject credentials from your vault."}
        </p>
        <div className="mt-auto border-t border-border/40 pt-3" onClick={(e) => e.stopPropagation()}>
          {provider.status !== "available" ? (
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {provider.connectionCount} connection{provider.connectionCount !== 1 ? "s" : ""}
              </span>
              {provider.requiresNamedLogin ? (
                <Button
                  onClick={(e) => { e.preventDefault(); onNamedLogin(); }}
                  size="sm"
                  type="button"
                  variant="ghost"
                >
                  <Plus className="size-3.5" />
                  Add
                </Button>
              ) : (
                <form action={`/api/auth/providers/${provider.name}/connect`} method="post">
                  <input name="connection" type="hidden" value="default" />
                  <input name="return_url" type="hidden" value="/connections" />
                  <Button size="sm" type="submit" variant="ghost">
                    <Plus className="size-3.5" />
                    Add
                  </Button>
                </form>
              )}
            </div>
          ) : provider.requiresNamedLogin ? (
            <Button
              className="w-full"
              onClick={(e) => { e.preventDefault(); onNamedLogin(); }}
              size="sm"
              type="button"
            >
              <LogIn />
              Connect
            </Button>
          ) : (
            <form action={`/api/auth/providers/${provider.name}/connect`} method="post">
              <input name="connection" type="hidden" value="default" />
              <input name="return_url" type="hidden" value="/connections" />
              <Button className="w-full" size="sm" type="submit">
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

function DeleteCustomProviderDialog({
  onDeleted,
  onOpenChange,
  provider,
}: {
  onDeleted: () => void;
  onOpenChange: (open: boolean) => void;
  provider: ProviderView | null;
}) {
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");

  async function deleteProviderDefinition() {
    if (!provider) return;
    setWorking(true);
    setMessage("");
    try {
      await deleteCustomProvider(provider.name);
      onDeleted();
      onOpenChange(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Provider could not be deleted.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <Dialog onOpenChange={onOpenChange} open={Boolean(provider)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete custom provider</DialogTitle>
          <DialogDescription>
            {provider?.connectionCount
              ? `${provider.displayName} has ${provider.connectionCount} connection${provider.connectionCount === 1 ? "" : "s"}. Deleting it will revoke those credentials first.`
              : `${provider?.displayName || "This provider"} will be removed from custom providers.`}
          </DialogDescription>
        </DialogHeader>
        {message ? <div className="text-sm text-destructive">{message}</div> : null}
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)} type="button" variant="outline">
            Cancel
          </Button>
          <Button disabled={working} onClick={() => void deleteProviderDefinition()} type="button" variant="destructive">
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export type NamedConnectionProvider = Pick<ProviderView, "displayName" | "name">;

export function NamedConnectionDialog({
  onOpenChange,
  provider,
}: {
  onOpenChange: (provider: NamedConnectionProvider | null) => void;
  provider: NamedConnectionProvider | null;
}) {
  const [connectionName, setConnectionName] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    if (!connectionName.trim()) {
      event.preventDefault();
    }
  }

  return (
    <Dialog
      open={Boolean(provider)}
      onOpenChange={(open) => {
        if (!open) {
          setConnectionName("");
        }
        onOpenChange(open ? provider : null);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connection name</DialogTitle>
          <DialogDescription>{provider?.displayName} already has a default connection.</DialogDescription>
        </DialogHeader>
        <form
          action={provider ? `/api/auth/providers/${provider.name}/connect` : "#"}
          className="grid gap-3"
          method="post"
          onSubmit={handleSubmit}
        >
          <input name="return_url" type="hidden" value="/connections" />
          <label className="grid gap-1.5 text-sm">
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
