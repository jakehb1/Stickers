FROM nginx:1.25-alpine

COPY apps/mini-app/ /usr/share/nginx/html/
COPY apps/admin-dashboard/ /usr/share/nginx/html/admin/
COPY frontend/nginx.conf /etc/nginx/nginx.conf
COPY frontend/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80

CMD ["/entrypoint.sh"]
