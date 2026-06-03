import { Suspense } from "react";

import { AuthsomeSessionDeviceFromUrl } from "@/components/authsome-dashboard";

export default function AuthDevicePage() {
  return (
    <Suspense fallback={null}>
      <AuthsomeSessionDeviceFromUrl />
    </Suspense>
  );
}
