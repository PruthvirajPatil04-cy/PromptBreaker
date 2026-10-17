/** @type {import('next').NextConfig} */
const API_ORIGIN = process.env.PB_API_ORIGIN ?? "http://127.0.0.1:8000";
const nextConfig = {
  reactStrictMode: true,
  // 'standalone' emits a self-contained .next/standalone server (node + traced
  // node_modules only) — that is what the offline Windows bundle ships. The
  // normal `next start` path used by systemd is unaffected.
  output: "standalone",
  // Single-origin deployment: the dashboard proxies the engine, so one URL
  // (local or tunnel) serves the entire app with no CORS and no second
  // hostname to share. The API origin stays a server-side detail.
  async rewrites() {
    return [
      { source: "/v1/:path*", destination: `${API_ORIGIN}/v1/:path*` },
      { source: "/metrics", destination: `${API_ORIGIN}/metrics` },
      { source: "/healthz", destination: `${API_ORIGIN}/healthz` },
    ];
  },
};
module.exports = nextConfig;
