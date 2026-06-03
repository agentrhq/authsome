import { Suspense } from "react";

import { AuthsomeSessionSuccessFromUrl } from "@/components/authsome-dashboard";

export default function AuthSuccessPage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeSessionSuccessFromUrl />
    </Suspense>
  );
}
