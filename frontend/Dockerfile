# Usa un'immagine Nginx leggera per servire i file statici
FROM nginx:stable-alpine

# Copia i file del frontend nella cartella di default di Nginx
COPY . /usr/share/nginx/html

# Esponi la porta 80
EXPOSE 80

# Comando per avviare Nginx
CMD ["nginx", "-g", "daemon off;"]
