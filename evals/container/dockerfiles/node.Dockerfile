FROM node:24-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev --ignore-scripts
COPY . .
ENV PORT=3000
EXPOSE $PORT
CMD ["npm", "start"]
