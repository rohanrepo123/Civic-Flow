FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@12.3.4 --activate
COPY frontend_member1/package.json frontend_member1/pnpm-lock.yaml frontend_member1/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend_member1/ ./
ARG NEXT_PUBLIC_CORE_API_URL=http://localhost:8010
ARG NEXT_PUBLIC_BROWSER_AGENT_URL=http://localhost:8012
ENV NEXT_PUBLIC_CORE_API_URL=$NEXT_PUBLIC_CORE_API_URL
ENV NEXT_PUBLIC_BROWSER_AGENT_URL=$NEXT_PUBLIC_BROWSER_AGENT_URL
RUN pnpm build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
RUN corepack enable && corepack prepare pnpm@12.3.4 --activate
COPY --from=build /app ./
EXPOSE 3000
CMD ["pnpm", "start", "--", "--hostname", "0.0.0.0"]
