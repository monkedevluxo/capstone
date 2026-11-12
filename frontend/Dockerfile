# Dashboard de SentinelAI.
#
# bun solo instala las dependencias; Next.js se ejecuta con Node. Las dos
# etapas usan Alpine (musl) para que los binarios nativos que baja bun
# (SWC, lightningcss, el motor de Tailwind) sirvan en la etapa de Node.

FROM oven/bun:1.4.4-alpine AS deps
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Desarrollo: lo usa docker-compose, con el código montado en vivo.
FROM node:24-alpine AS dev
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["node_modules/.bin/next", "dev", "--hostname", "0.0.0.0", "--port", "3000"]
