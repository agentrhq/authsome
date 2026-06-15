import { Suspense } from "react";

import { AuthsomeSessionSuccessFromUrl } from "@/components/dashboard/auth-flows";

export default function AuthSuccessPage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeSessionSuccessFromUrl />
    </Suspense>
  );
}
