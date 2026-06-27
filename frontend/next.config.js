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
      {
        source: "/api/students/:path*",
        destination: `${BACKEND_URL}/students/:path*`,
      },
      {
        source: "/api/academic/:path*",
        destination: `${BACKEND_URL}/academic/:path*`,
      },
      {
        source: "/api/schedule/:path*",
        destination: `${BACKEND_URL}/schedule/:path*`,
      },
      {
        source: "/api/suggestions/:path*",
        destination: `${BACKEND_URL}/suggestions/:path*`,
      },
      {
        source: "/api/conversations/:path*",
        destination: `${BACKEND_URL}/conversations/:path*`,
      },
      {
        source: "/api/tickets/:path*",
        destination: `${BACKEND_URL}/tickets/:path*`,
      },
      {
        source: "/api/admin/tickets/:path*",
        destination: `${BACKEND_URL}/admin/tickets/:path*`,
      },
      {
        source: "/api/admin/dashboard",
        destination: `${BACKEND_URL}/admin/dashboard`,
      },
      {
        source: "/api/admin/notifications/:path*",
        destination: `${BACKEND_URL}/admin/notifications/:path*`,
      },
      {
        source: "/api/forum/:path*",
        destination: `${BACKEND_URL}/forum/:path*`,
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
