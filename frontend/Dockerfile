FROM nginx:1.25-alpine

COPY mini-app/ /usr/share/nginx/html/
COPY admin/ /usr/share/nginx/html/admin/
COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80

CMD ["/entrypoint.sh"]
