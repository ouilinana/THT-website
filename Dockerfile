FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY *.html /srv/
COPY en /srv/en/
COPY assets /srv/assets/
COPY sitemap.xml robots.txt /srv/

EXPOSE 8080
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
