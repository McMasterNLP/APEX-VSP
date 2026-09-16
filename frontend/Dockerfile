# Multi-stage: build Vite SPA, serve static assets with nginx.

FROM node:22-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
# package-lock.json is generated on macOS dev machines, so its resolved
# optionalDependencies entries only cover macOS's native rollup binary.
# Both `npm ci` and `npm install` respect an existing lockfile's already-resolved
# optional deps and won't add a missing Linux entry on their own (a known npm
# bug: https://github.com/npm/cli/issues/4828). Deleting the lockfile here (this
# only affects this build layer, not the committed file) forces npm to resolve
# everything fresh for the actual Linux build platform.
RUN rm -f package-lock.json && npm install

COPY . .

ARG VITE_API_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY

ENV VITE_API_URL=${VITE_API_URL} \
    VITE_SUPABASE_URL=${VITE_SUPABASE_URL} \
    VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}

RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
