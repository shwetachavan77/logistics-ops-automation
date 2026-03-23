FROM nginx:alpine

# Copy dashboard files
COPY public/ /usr/share/nginx/html/

# Nginx config to proxy /api to backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
