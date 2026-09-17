FROM python:3.12-slim AS api
WORKDIR /app
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt
COPY api ./api
COPY mcp_layer ./mcp_layer
COPY reclaim ./reclaim
COPY scripts ./scripts
COPY starter/claims.schema.json ./starter/claims.schema.json
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "reclaim.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM node:22-alpine AS frontend-build
WORKDIR /app
COPY dashboard/package*.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ .
RUN npm run build

FROM nginx:alpine AS dashboard
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html
EXPOSE 3000
