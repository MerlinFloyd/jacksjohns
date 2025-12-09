# Discord Bot Dockerfile
# Bun runtime with TypeScript

FROM oven/bun:1.1-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json bun.lockb* ./

# Install dependencies
RUN bun install --frozen-lockfile || bun install

# Copy TypeScript config and source
COPY tsconfig.json ./
COPY src/ ./src/

# Build TypeScript (optional - Bun can run TS directly)
# RUN bun build ./src/index.ts --outdir ./dist --target bun

# Run the bot
CMD ["bun", "run", "src/index.ts"]
