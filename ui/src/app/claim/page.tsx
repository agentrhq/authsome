import { Suspense } from "react";

import { AuthsomeClaimFromUrl } from "@/components/dashboard/auth-flows";

export default function ClaimPage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeClaimFromUrl />
    </Suspense>
  );
}
