/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Single-origin deployment: the dashboard proxies the engine, so one URL
  // (local or tunnel) serves the entire app with no CORS and no second
  // hostname to share. The API origin stays a server-side detail.
  async rewrites() {
    return [
      { source: "/v1/:path*", destination: "http://127.0.0.1:8000/v1/:path*" },
      { source: "/healthz", destination: "http://127.0.0.1:8000/healthz" },
    ];
  },
};
module.exports = nextConfig;
