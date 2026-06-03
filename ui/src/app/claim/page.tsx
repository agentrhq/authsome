import { Suspense } from "react";

import { AuthsomeClaimFromUrl } from "@/components/authsome-dashboard";

export default function ClaimPage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeClaimFromUrl />
    </Suspense>
  );
}
