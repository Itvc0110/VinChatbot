/** @type {import('next').NextConfig} */

// The browser talks to FastAPI through /api/* rewrites, so there is no CORS change
// on the Python side and no provider SDK ever reaches the client.
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/auth/:path*",
        destination: `${BACKEND_URL}/auth/:path*`,
      },
      // Order matters: the more specific /stream rule must precede the catch-all /chat.
      {
        source: "/api/chat/stream",
        destination: `${BACKEND_URL}/chat/stream`,
      },
      {
        source: "/api/chat",
        destination: `${BACKEND_URL}/chat`,
      },
      // Admin/knowledge endpoints proxied to FastAPI (GET /sources, POST /ingest/run).
      {
        source: "/api/sources",
        destination: `${BACKEND_URL}/sources`,
      },
      {
        source: "/api/ingest/run",
        destination: `${BACKEND_URL}/ingest/run`,
      },
    ];
  },
};

module.exports = nextConfig;
