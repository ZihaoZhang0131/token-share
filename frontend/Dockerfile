FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend .
RUN npm run build

FROM nginx:1.27-alpine
RUN apk add --no-cache gettext
COPY --from=build /src/dist /usr/share/nginx/html
COPY deploy/nginx/http.conf.template /opt/token-station/http.conf.template
COPY deploy/nginx/https.conf.template /opt/token-station/https.conf.template
COPY deploy/nginx/entrypoint.sh /opt/token-station/entrypoint.sh
RUN chmod 755 /opt/token-station/entrypoint.sh
ENTRYPOINT ["/opt/token-station/entrypoint.sh"]
