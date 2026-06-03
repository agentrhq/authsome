import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

const nextConfig: NextConfig = {
  ...(!isDev && { output: "export" }),
  trailingSlash: true,
  ...(isDev && {
    async rewrites() {
      // Proxy daemon API paths to the local daemon during development.
      // In production the static export is served directly by the daemon.
      const DAEMON = "http://127.0.0.1:7998";
      return [
        { source: "/api/:path*", destination: `${DAEMON}/api/:path*` },
      ];
    },
  }),
};

export default nextConfig;
