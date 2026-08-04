# BOTMARKET frontend image (Next.js)
FROM node:20-alpine

WORKDIR /app

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./

EXPOSE 3000
CMD ["npm", "run", "dev"]
