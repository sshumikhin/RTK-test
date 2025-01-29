FROM nginx:latest

RUN apt-get update && apt-get install -y openssl

RUN openssl req -x509 -newkey rsa:2048 -nodes -keyout /etc/nginx/cert.key -out /etc/nginx/cert.crt -days 365 -subj "/C=RU/ST=State/L=Locality/O=Organization/CN=localhost"

COPY nginx.conf /etc/nginx/nginx.conf

CMD ["nginx", "-g", "daemon off;"]
