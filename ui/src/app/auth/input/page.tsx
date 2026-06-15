import { Suspense } from "react";

import { AuthsomeSessionInputFromUrl } from "@/components/dashboard/auth-flows";

export default function AuthInputPage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeSessionInputFromUrl />
    </Suspense>
  );
}
