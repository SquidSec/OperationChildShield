# Pin to Node 22 LTS. Node 26 is too new for reliable Next.js production images.
FROM node:22-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json package-lock.json ./
# Prefer npm ci when lock matches package.json. Fall back to npm install when
# Dependabot (or a partial pin) leaves them out of sync.
RUN npm ci || npm install

COPY . .
# Hero flag is stored as base64 text in git (split segments for easier commits).
# Decode before `next build` so the file is part of the public/ standalone output.
RUN set -e; \
    if [ -f public/images/american_flag.jpg.b64 ]; then \
      base64 -d public/images/american_flag.jpg.b64 > public/images/american_flag.jpg; \
    elif [ -f public/images/american_flag.jpg.b64.s0 ]; then \
      cat public/images/american_flag.jpg.b64.s0 \
          public/images/american_flag.jpg.b64.s1 \
          public/images/american_flag.jpg.b64.s2 \
          public/images/american_flag.jpg.b64.s3 \
        | tr -d '\n' \
        | base64 -d > public/images/american_flag.jpg; \
    fi
ENV NODE_OPTIONS=--max-old-space-size=2048
RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
