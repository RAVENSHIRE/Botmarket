# BOTMARKET frontend image (Next.js)
FROM node:20-alpine

WORKDIR /app

# Install from the lockfile so the image matches local development exactly.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

EXPOSE 3000
CMD ["npm", "run", "dev"]
