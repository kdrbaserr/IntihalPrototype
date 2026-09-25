FROM node:22-alpine AS base

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

FROM base AS dependencies

COPY package.json package-lock.json ./
RUN npm ci

FROM dependencies AS development

ENV NODE_ENV=development

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

FROM dependencies AS builder

COPY . .
RUN npm run build

FROM node:22-alpine AS production

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
