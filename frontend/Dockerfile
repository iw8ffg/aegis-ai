# Fase 1: Build dell'applicazione React/Vue
FROM node:18 as build

WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

# Fase 2: Servire l'applicazione con Nginx
FROM nginx:stable-alpine
COPY --from=build /app/build /usr/share/nginx/html

# Esponi la porta 80
EXPOSE 80

# Comando per avviare Nginx
CMD ["nginx", "-g", "daemon off;"]
