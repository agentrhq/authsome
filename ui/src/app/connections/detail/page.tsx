import { Suspense } from "react";

import { AuthsomeConnectionDetailRoute } from "@/components/authsome-dashboard";

export default function ConnectionDetailPage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeConnectionDetailRoute />
    </Suspense>
  );
}
