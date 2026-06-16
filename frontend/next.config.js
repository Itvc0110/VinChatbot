/** @type {import('next').NextConfig} */

// The browser only ever talks to FastAPI's /chat contract. We proxy /api/chat to the
// backend so there is no CORS change on the Python side and the hinge rule holds:
// the UI never imports an LLM SDK — it calls the FastAPI route, full stop.
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/chat",
        destination: `${BACKEND_URL}/chat`,
      },
    ];
  },
};

module.exports = nextConfig;
