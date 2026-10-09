FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci --cache /tmp/mgai-npm-cache --no-audit --no-fund; else npm ci --cache /tmp/mgai-npm-cache --no-audit --no-fund; fi \
    && rm -rf /tmp/mgai-npm-cache
COPY frontend ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 STATIC_DIR=/app/static
RUN groupadd --gid 10001 mgai && useradd --uid 10001 --gid 10001 --no-create-home mgai
WORKDIR /app
COPY backend/requirements.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca python -m pip install --no-cache-dir --require-hashes -r requirements.lock; else python -m pip install --no-cache-dir --require-hashes -r requirements.lock; fi
COPY --chown=10001:10001 backend/mgai ./mgai
COPY --chown=10001:10001 backend/alembic.ini ./
COPY --chown=10001:10001 backend/migrations ./migrations
COPY --from=frontend --chown=10001:10001 /build/dist ./static
USER 10001:10001
EXPOSE 8000
CMD ["python","-m","uvicorn","mgai.asgi:app","--host","0.0.0.0","--port","8000","--workers","1","--no-access-log","--proxy-headers"]
