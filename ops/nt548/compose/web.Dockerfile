# Web image: the built SPA served by web/server.mjs (proxies /api/harness/* to 127.0.0.1:HARNESS_PORT).
# Build context: repo root; only web/ goes in (web.Dockerfile.dockerignore). web/public/data is not in git, so the
# image has no place data until the sample data (T5) provides it.
#   docker build -f ops/nt548/compose/web.Dockerfile -t web .
FROM node:24-slim AS build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build:prod

FROM node:24-slim
ENV NODE_ENV=production PORT=8080 HARNESS_PORT=8769
WORKDIR /app/web
COPY --from=build /app/web/dist dist
COPY web/server.mjs server.mjs
ARG REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/LuanLuKim/tripguardian-nt548" \
      org.opencontainers.image.revision="${REVISION}"
USER node
EXPOSE 8080
CMD ["node", "server.mjs"]
