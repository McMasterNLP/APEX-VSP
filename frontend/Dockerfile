# Multi-stage: build Vite SPA, serve static assets with nginx.

FROM node:22-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
# npm ci strictly installs what's locked, including platform-specific optional
# native binaries (e.g. rollup's @rollup/rollup-linux-*). Since package-lock.json
# is generated on macOS dev machines, that resolution doesn't carry over cleanly
# to this Linux build image (a known npm bug: https://github.com/npm/cli/issues/4828).
# npm install re-resolves optional deps for the actual build platform.
RUN npm install

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
