# syntax=docker/dockerfile:1

# Imagen multi-stage para la web Next.js 16 (App Router) con salida standalone.
# Build context esperado: la carpeta web/ (raíz del proyecto Next).

# ---- deps: instala dependencias con bun a partir del lockfile ----
FROM oven/bun:1.2-alpine AS deps
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# ---- builder: compila la app (NEXT_PUBLIC_* vienen de .env.production) ----
FROM oven/bun:1.2-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN bun run build

# ---- runner: imagen final mínima con el server standalone sobre node ----
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup -g 1001 -S nodejs \
    && adduser -S nextjs -u 1001

# public/ no se incluye en standalone: se copia aparte.
COPY --from=builder /app/public ./public
# server.js + node_modules mínimos trazados por Next.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# assets estáticos (_next/static) que sirve el propio server.js.
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
