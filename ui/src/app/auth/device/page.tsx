import { Suspense } from "react";

import { AuthsomeSessionDeviceFromUrl } from "@/components/dashboard/auth-flows";

export default function AuthDevicePage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeSessionDeviceFromUrl />
    </Suspense>
  );
}
