"use client";

import { LogIn, Pencil, Plus, Trash2 } from "lucide-react";
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
  const [dialogProvider, setDialogProvider] = useState<NamedConnectionProvider | null>(null);
  const [formState, setFormState] = useState<{ mode: "create" | "edit"; provider?: ProviderView } | null>(null);
  const [deleteProvider, setDeleteProvider] = useState<ProviderView | null>(null);

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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeader description="Configure providers and start browser login flows." title="Providers" />
        {isAdmin ? (
          <Button onClick={() => setFormState({ mode: "create" })} type="button">
            <Plus />
            New provider
          </Button>
        ) : null}
      </div>
      <SearchInput onChange={setQuery} placeholder="Search providers..." value={query} />
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
        query.trim() ? (
          <PageEmptyState
            actionLabel="Clear search"
            onAction={() => setQuery("")}
            title="No providers found"
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
        <div className="flex items-start justify-between gap-3">
          <ProviderLogo className="size-10 shrink-0" initial={provider.logoInitial} logo={provider.logo} />
          <div className="flex items-center gap-1.5">
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
        <div className="mt-1">
          <CardTitle className="text-base leading-tight">{provider.displayName}</CardTitle>
          <CardDescription className="mt-0.5 text-xs">
            {provider.source === "custom" ? "Custom provider" : "Bundled provider"}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4 pt-0">
        <p className="line-clamp-2 min-h-12 text-sm leading-relaxed text-muted-foreground">
          {provider.description || "Connect this provider to store and inject credentials from your Authsome vault."}
        </p>
        <div className="flex min-h-7 flex-wrap content-start gap-1.5">
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
              <input name="return_url" type="hidden" value="/connections" />
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
          className="grid gap-4"
          method="post"
          onSubmit={handleSubmit}
        >
          <input name="return_url" type="hidden" value="/connections" />
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
