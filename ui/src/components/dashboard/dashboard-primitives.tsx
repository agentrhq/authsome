"use client";

import { CheckCircle2, CircleAlert, Search } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export const INTERACTIVE_CARD_CLASS =
  "cursor-pointer border border-border/50 shadow-none transition-all hover:border-primary/60 hover:bg-primary/[0.03] hover:shadow-sm";
export const INTERACTIVE_ROW_CLASS =
  "cursor-pointer transition-colors hover:bg-primary/[0.03] focus-visible:bg-primary/[0.03] focus-visible:outline-none";

export function ProviderLogo({
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
    return `https://${logo}`;
  }
  return logo;
}

export function StatusBadge({ status }: { status: string }) {
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

export function connectionDetailHref(provider: string, connection: string, principal?: string | null): string {
  const params = new URLSearchParams({ provider, connection });
  if (principal) {
    params.set("principal", principal);
  }
  return `/connections/detail?${params.toString()}`;
}

export function providerDetailHref(provider: string): string {
  return `/providers/detail?${new URLSearchParams({ provider }).toString()}`;
}

export function SearchInput({
  onChange,
  placeholder,
  value,
}: {
  onChange: (value: string) => void;
  placeholder: string;
  value: string;
}) {
  return (
    <label className="relative block w-full">
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

export function KeyValue({ label, value }: { label: string; value: string }) {
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
