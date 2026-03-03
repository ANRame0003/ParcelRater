FROM nginx:1.27-alpine

# Copy the single-page app
COPY index.html /usr/share/nginx/html/index.html

# Replace default nginx config with ours
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
