import { Suspense } from "react";

import { AuthsomeProviderDetailRoute } from "@/components/authsome-dashboard";

export default function ProviderDetailPage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeProviderDetailRoute />
    </Suspense>
  );
}
