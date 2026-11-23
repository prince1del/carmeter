# MeterDigit — Next.js UI + Python digit renderer
FROM node:20-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-bookworm-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=43129
ENV HOSTNAME=0.0.0.0

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
  && rm -rf /var/lib/apt/lists/* \
  && python3 -m pip install --no-cache-dir --break-system-packages \
    "psd-tools>=1.9" "pillow>=10" "openpyxl>=3.1" "numpy>=1.26"

RUN groupadd --system --gid 1001 nodejs \
  && useradd --system --uid 1001 --gid nodejs nextjs

COPY --from=builder /app/package.json ./
COPY --from=builder /app/package-lock.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.ts ./
COPY --from=builder /app/tsconfig.json ./
COPY --from=builder /app/scripts ./scripts
COPY --from=builder /app/data ./data
# digit-cache may ship as a single tarball (GitHub web upload limit)
RUN if [ -f ./data/digit-cache.tgz ]; then       tar -xzf ./data/digit-cache.tgz -C ./data && rm -f ./data/digit-cache.tgz;     fi
COPY --from=builder /app/templates ./templates
COPY --from=builder /app/requirements.txt ./

# Next generate API writes temp jobs — need writable dirs
RUN mkdir -p /tmp/meterdigit && chown -R nextjs:nodejs /app /tmp/meterdigit

USER nextjs
EXPOSE 43129
CMD ["npx", "next", "start", "--port", "43129", "--hostname", "0.0.0.0"]
