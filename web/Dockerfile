FROM node:20-alpine
WORKDIR /app
COPY web/package*.json ./
RUN npm install
COPY web /app
CMD ["npm", "run", "dev"]
