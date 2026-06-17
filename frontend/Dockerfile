# Frontend (Next.js 14) image. Multi-stage: deps -> build -> runner.
# The server-side rewrite in next.config.js reads BACKEND_URL at runtime, so the
# browser only ever talks to this service; /api/chat is proxied to the backend
# over the internal compose network.
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS build
WORKDIR /app
# next.config.js resolves rewrites() at build time and bakes the destination into the
# routes manifest, so BACKEND_URL must be present HERE (not just at runtime) or the
# proxy falls back to localhost:8000 and /api/chat fails with ECONNREFUSED.
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . ./
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.js ./next.config.js
EXPOSE 3000
CMD ["npm", "start"]
