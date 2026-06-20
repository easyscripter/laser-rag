FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- Runtime: serve the static build with `serve` (no nginx) ----
FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
# `serve` is a tiny static file server; -s enables SPA fallback (React Router).
RUN npm install -g serve@14

COPY --from=builder /app/dist ./dist

EXPOSE 5173

CMD ["serve", "-s", "dist", "-l", "5173"]
