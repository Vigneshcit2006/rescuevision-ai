# RescueVision AI - frontend image
# Stage 1: build the Vite/React/TypeScript app.
FROM node:20-slim AS build

WORKDIR /app

# The API base URL is baked into the static bundle at build time by Vite
# (import.meta.env.VITE_API_BASE_URL, see frontend/src/api.ts).
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY package*.json ./
# Use npm ci when a lockfile is present, fall back to npm install otherwise
# (this project may not have committed a package-lock.json yet).
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

# Stage 2: serve the static build with nginx.
FROM nginx:alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
