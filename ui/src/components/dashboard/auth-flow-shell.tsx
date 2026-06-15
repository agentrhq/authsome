"use client";

import Image from "next/image";
import { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function AuthFlowShell({
  children,
  description,
  size = "compact",
  title,
}: {
  children?: ReactNode;
  description: string;
  size?: "compact" | "wide";
  title: string;
}) {
  if (size === "wide") {
    return (
      <main className="flex min-h-screen items-center bg-background px-4 py-8 sm:px-6 lg:px-10">
        <section className="mx-auto grid w-full max-w-6xl gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div className="max-w-md">
            <Image alt="Authsome" className="mb-8 size-11" height={44} src="/logo.svg" width={44} />
            <h1 className="text-4xl font-semibold leading-tight text-foreground">{title}</h1>
            <p className="mt-4 text-base leading-7 text-muted-foreground">{description}</p>
          </div>
          <div>{children}</div>
        </section>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center bg-background px-4 py-8 sm:px-6 lg:px-10">
      <section className="mx-auto w-full max-w-md">
        <Card className="border-border/70 shadow-none">
          <CardHeader>
            <Image alt="Authsome" className="mb-4 size-9" height={36} src="/logo.svg" width={36} />
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          {children ? <CardContent>{children}</CardContent> : null}
        </Card>
      </section>
    </main>
  );
}
