import Link from "next/link";
import { ArrowLeft, CircleAlert } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <Card className="w-full max-w-md border-border/70 shadow-none">
        <CardHeader>
          <div className="mb-3 flex size-10 items-center justify-center rounded-lg border border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-400" aria-hidden="true">
            <CircleAlert className="size-5" />
          </div>
          <CardTitle>Page not found</CardTitle>
          <CardDescription>The dashboard route is missing or no longer available.</CardDescription>
        </CardHeader>
        <CardContent>
          <Link className={buttonVariants()} href="/">
            <ArrowLeft />
            Back to dashboard
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}
