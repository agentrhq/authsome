import { ApiError } from "@/lib/authsome-api";

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export function currentBrowserPath(fallback: string): string {
  if (typeof window === "undefined") {
    return fallback;
  }
  return `${window.location.pathname}${window.location.search}`;
}
