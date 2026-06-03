import { Suspense } from "react";

import { AuthsomeSessionInputFromUrl } from "@/components/authsome-dashboard";

export default function AuthInputPage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeSessionInputFromUrl />
    </Suspense>
  );
}
