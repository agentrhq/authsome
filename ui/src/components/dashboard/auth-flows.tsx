"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CheckCircle2, CircleAlert, LogIn, UserRound } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";

import { AuthFlowShell } from "@/components/dashboard/auth-flow-shell";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  SessionInputField,
  fetchAuthSessionStatus,
  fetchClaimStatus,
  fetchSessionDevice,
  fetchSessionInput,
} from "@/lib/authsome-api";
import { cn } from "@/lib/utils";

const NEXT_URL = "/";
const ADVANCED_SESSION_FIELD_NAMES = new Set(["host_url", "base_url", "api_url", "scopes"]);

export function AuthsomeLogin({ nextPath = NEXT_URL }: { nextPath?: string }) {
  const [safeNextPath] = useState(() => {
    if (typeof window === "undefined") {
      return nextPath;
    }
    const next = new URLSearchParams(window.location.search).get("next") || nextPath;
    return next.startsWith("/") && !next.startsWith("//") ? next : NEXT_URL;
  });

  const [errorMessage] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("error") || "";
  });

  const [defaultTab] = useState(() => {
    if (typeof window === "undefined") return "signin";
    const tab = new URLSearchParams(window.location.search).get("tab");
    return tab === "register" ? "create" : "signin";
  });

  const [mode, setMode] = useState<"signin" | "create">(defaultTab === "create" ? "create" : "signin");
  const isSignIn = mode === "signin";

  return (
    <AuthFlowShell
      description="Manage credentials, connected providers, and agent access from a single dashboard."
      size="wide"
      title="Authsome"
    >
      <Card className="overflow-hidden border-border/50 shadow-lg shadow-black/5 dark:shadow-black/20">
        <CardHeader className="space-y-1 pb-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={mode}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.15 }}
            >
              <CardTitle className="text-xl font-semibold tracking-tight">
                {isSignIn ? "Sign in" : "Create account"}
              </CardTitle>
              <CardDescription className="mt-1">
                {isSignIn
                  ? "Enter your credentials to access the dashboard."
                  : "Set up a new account to get started."}
              </CardDescription>
            </motion.div>
          </AnimatePresence>
        </CardHeader>
        <CardContent className="pb-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={mode}
              initial={{ opacity: 0, x: isSignIn ? -12 : 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: isSignIn ? 12 : -12 }}
              transition={{ duration: 0.2, ease: "easeInOut" as const }}
            >
              {errorMessage ? <ErrorBanner message={errorMessage} /> : null}
              <form
                action={isSignIn ? "/api/auth/login" : "/api/auth/register"}
                className="grid gap-5"
                method="post"
              >
                <input name="next" type="hidden" value={safeNextPath} />
                <div className="grid gap-2">
                  <label htmlFor="email" className="text-sm font-medium">
                    Email
                  </label>
                  <Input
                    id="email"
                    autoComplete="email"
                    className="h-10"
                    name="email"
                    placeholder="you@example.com"
                    required
                    type="email"
                  />
                </div>
                <div className="grid gap-2">
                  <label htmlFor="password" className="text-sm font-medium">
                    Password
                  </label>
                  <Input
                    id="password"
                    autoComplete={isSignIn ? "current-password" : "new-password"}
                    className="h-10"
                    minLength={8}
                    name="password"
                    placeholder={isSignIn ? "Enter your password" : "Min. 8 characters"}
                    required
                    type="password"
                  />
                </div>
                <Button className="mt-2 h-10 w-full text-sm font-semibold" type="submit" size="lg">
                  {isSignIn ? "Sign in" : "Create account"}
                  <ArrowRight className="size-4" />
                </Button>
              </form>
            </motion.div>
          </AnimatePresence>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            {isSignIn ? "Don’t have an account?" : "Already have an account?"}{" "}
            <button
              type="button"
              className="font-medium text-primary underline-offset-4 hover:underline"
              onClick={() => setMode(isSignIn ? "create" : "signin")}
            >
              {isSignIn ? "Create one" : "Sign in"}
            </button>
          </div>
        </CardContent>
      </Card>
    </AuthFlowShell>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <motion.div
      className="mb-1 flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm text-destructive"
      role="alert"
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      transition={{ duration: 0.2 }}
    >
      <CircleAlert className="size-4 shrink-0" aria-hidden="true" />
      {message}
    </motion.div>
  );
}

export function AuthsomeClaim({ token }: { token: string }) {
  const { data, error } = useSWR(token ? ["authsome-claim", token] : null, () => fetchClaimStatus(token));
  const nextPath = token ? `/claim?token=${encodeURIComponent(token)}` : "/claim";

  if (!token) {
    return (
      <AuthFlowShell
        description="The claim link is missing a token."
        title="Invalid claim link"
      />
    );
  }

  if (error) {
    return (
      <AuthFlowShell
        description="This claim link could not be loaded. Request a new link from the CLI."
        title="Claim unavailable"
      />
    );
  }

  if (!data) {
    return (
      <AuthFlowShell
        description="Checking this agent claim."
        title="Loading claim"
      />
    );
  }

  if (data.expired) {
    return (
      <AuthFlowShell
        description="This claim link has expired. Request a new link from the CLI."
        title="Claim expired"
      />
    );
  }

  if (!data.authenticated) {
    return <AuthsomeLogin nextPath={nextPath} />;
  }

  return (
    <AuthFlowShell
      description={`Confirm that ${data.identity} should be linked to ${data.email || "this account"}.`}
      title="Claim agent"
    >
      <form action={`/api/claim/${encodeURIComponent(token)}/confirm`} method="post">
        <Button className="w-full" type="submit">
          <UserRound />
          Confirm claim
        </Button>
      </form>
    </AuthFlowShell>
  );
}

export function AuthsomeClaimFromUrl() {
  const searchParams = useSearchParams();
  return <AuthsomeClaim token={searchParams.get("token") || ""} />;
}

export function AuthsomeSessionInputFromUrl() {
  const searchParams = useSearchParams();
  return <AuthsomeSessionInput sessionId={searchParams.get("session") || ""} />;
}

export function AuthsomeSessionDeviceFromUrl() {
  const searchParams = useSearchParams();
  return <AuthsomeSessionDevice sessionId={searchParams.get("session") || ""} />;
}

export function AuthsomeSessionSuccessFromUrl() {
  const searchParams = useSearchParams();
  return (
    <AuthsomeSessionSuccess
      errorCode={searchParams.get("error") || ""}
      sessionId={searchParams.get("session") || ""}
    />
  );
}

function AuthsomeSessionInput({ sessionId }: { sessionId: string }) {
  const { data, error } = useSWR(sessionId ? ["authsome-session-input", sessionId] : null, () =>
    fetchSessionInput(sessionId),
  );

  if (!sessionId) {
    return (
      <AuthFlowShell
        description="The provider setup link is missing a session identifier."
        title="Invalid setup link"
      />
    );
  }

  if (error) {
    return (
      <AuthFlowShell
        description="This provider setup session could not be loaded. Start the login flow again."
        title="Setup unavailable"
      />
    );
  }

  if (!data) {
    return (
      <AuthFlowShell
        description="Loading the provider setup fields."
        title="Loading setup"
      />
    );
  }

  const primaryFields = data.fields.filter((field) => !ADVANCED_SESSION_FIELD_NAMES.has(field.name));
  const advancedFields = data.fields.filter((field) => ADVANCED_SESSION_FIELD_NAMES.has(field.name));

  return (
    <AuthFlowShell
      description="Enter the provider details required to continue this login flow."
      title={data.display_name}
    >
      <form action={`/auth/input?session=${encodeURIComponent(sessionId)}`} className="grid gap-3" method="post">
        {data.warning ? (
          <div className="rounded-lg border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
            {data.warning}
          </div>
        ) : null}
        {data.callback_url ? (
          <label className="grid gap-1.5 text-sm">
            <span className="text-muted-foreground">OAuth callback URL</span>
            <Input readOnly value={data.callback_url} />
          </label>
        ) : null}
        {primaryFields.map((field) => (
          <SessionInputFieldControl field={field} key={field.name} />
        ))}
        {advancedFields.length ? (
          <details className="rounded-lg border bg-muted/20 p-3">
            <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
              Advanced
            </summary>
            <div className="mt-3 grid gap-3">
              {advancedFields.map((field) => (
                <SessionInputFieldControl field={field} key={field.name} />
              ))}
            </div>
          </details>
        ) : null}
        <Button className="mt-1 w-full" type="submit">
          <LogIn />
          Continue
        </Button>
      </form>
    </AuthFlowShell>
  );
}

function SessionInputFieldControl({ field }: { field: SessionInputField }) {
  return (
    <label className="grid gap-1.5 text-sm">
      <span className="text-muted-foreground">{field.label}</span>
      <Input
        defaultValue={field.default || ""}
        name={field.name}
        pattern={field.pattern || undefined}
        required={field.required !== false}
        type={field.secret ? "password" : "text"}
      />
      {field.pattern_hint ? (
        <span className="text-xs text-muted-foreground">{field.pattern_hint}</span>
      ) : null}
    </label>
  );
}

function AuthsomeSessionSuccess({ errorCode, sessionId }: { errorCode?: string; sessionId: string }) {
  const { data, error } = useSWR(sessionId ? ["authsome-session-status", sessionId] : null, () =>
    fetchAuthSessionStatus(sessionId),
  );

  if (errorCode) {
    const description =
      errorCode === "session_expired"
        ? "This authentication session expired. Start the login flow again."
        : "The provider callback did not include a valid authentication state.";
    return (
      <AuthFlowShell
        description={description}
        title="Login could not finish"
      />
    );
  }

  if (!sessionId) {
    return (
      <AuthFlowShell
        description="The completion link is missing a session identifier."
        title="Invalid session"
      />
    );
  }

  if (error) {
    return (
      <AuthFlowShell
        description="This login session could not be loaded. Check the terminal for the latest status."
        title="Session unavailable"
      />
    );
  }

  if (!data) {
    return (
      <AuthFlowShell
        description="Checking the latest login status."
        title="Finishing login"
      />
    );
  }

  const isCompleted = data.status === "completed";
  const isFailed = data.status === "failed";
  const title = isCompleted ? "Login complete" : isFailed ? "Login failed" : "Login in progress";
  const description = isCompleted
    ? `${data.provider} is connected as ${data.connection}.`
    : isFailed
      ? data.error || "The provider reported an authentication error."
      : data.message || "This provider is still finishing authentication.";

  return (
    <AuthFlowShell description={description} title={title}>
      <div className="grid gap-5">
        <div className="flex items-center gap-3 rounded-lg border bg-muted/25 px-4 py-3">
          <div
            className={cn(
              "flex size-10 shrink-0 items-center justify-center rounded-lg border",
              isCompleted
                ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400"
                : isFailed
                  ? "border-destructive/40 bg-destructive/10 text-destructive"
                  : "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-400",
            )}
            aria-hidden="true"
          >
            {isCompleted ? <CheckCircle2 /> : <CircleAlert />}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{data.provider}</p>
            <p className="truncate text-xs text-muted-foreground">{data.connection}</p>
          </div>
        </div>
        <Link className={buttonVariants()} href={isCompleted ? "/connections" : "/"}>
          {isCompleted ? "View connection" : "Back to dashboard"}
        </Link>
      </div>
    </AuthFlowShell>
  );
}

function AuthsomeSessionDevice({ sessionId }: { sessionId: string }) {
  const { data, error } = useSWR(sessionId ? ["authsome-session-device", sessionId] : null, () =>
    fetchSessionDevice(sessionId),
  );

  if (!sessionId) {
    return (
      <AuthFlowShell
        description="The device-code link is missing a session identifier."
        title="Invalid device link"
      />
    );
  }

  if (error) {
    return (
      <AuthFlowShell
        description="This device-code session could not be loaded. Start the login flow again."
        title="Device login unavailable"
      />
    );
  }

  if (!data) {
    return (
      <AuthFlowShell
        description="Loading the device-code login details."
        title="Loading device login"
      />
    );
  }

  return (
    <AuthFlowShell
      description={`Use this code to finish signing in to ${data.display_name}.`}
      title="Device login"
    >
      <div className="grid gap-3">
        <div className="rounded-lg border bg-muted/30 px-4 py-3 text-center font-mono text-2xl font-semibold">
          {data.user_code}
        </div>
        <Link
          className={buttonVariants()}
          href={data.verification_uri_complete || data.verification_uri}
          rel="noreferrer"
          target="_blank"
        >
          Open verification page
        </Link>
      </div>
    </AuthFlowShell>
  );
}
