"use client";

import { CircleAlert, Plus } from "lucide-react";
import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function PageEmptyState({
  actionLabel,
  description,
  href,
  onAction,
  title,
}: {
  actionLabel?: string;
  description?: string;
  href?: string;
  onAction?: () => void;
  title: string;
}) {
  const action = actionLabel
    ? href
      ? (
        <Link className={cn(buttonVariants({ size: "sm", variant: "outline" }), "mt-4")} href={href}>
          <Plus />
          {actionLabel}
        </Link>
      )
      : (
        <Button className="mt-4" onClick={onAction} size="sm" type="button" variant="outline">
          {actionLabel}
        </Button>
      )
    : null;

  return (
    <div className="rounded-lg border border-dashed bg-muted/40 p-6 text-center">
      <div className="text-sm font-medium">{title}</div>
      {description ? <p className="mt-1 text-xs text-muted-foreground">{description}</p> : null}
      {action}
    </div>
  );
}

export function PageErrorState({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-center text-sm text-destructive" role="alert">
      <CircleAlert className="size-4 shrink-0" aria-hidden="true" />
      {title}
    </div>
  );
}

export function PageLoadingState({ columns }: { columns: number }) {
  return (
    <div className="divide-y">
      {Array.from({ length: 3 }).map((_, row) => (
        <div className="grid gap-4 px-4 py-3 md:grid-cols-4" key={row}>
          {Array.from({ length: columns }).map((__, column) => (
            <Skeleton className="h-4 w-full max-w-48" key={column} />
          ))}
        </div>
      ))}
    </div>
  );
}
