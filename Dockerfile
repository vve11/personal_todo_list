FROM node:20-bookworm-slim AS frontend
WORKDIR /src/client
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend /src/client/dist ./client/dist
ENV PORT=10000
EXPOSE 10000
CMD ["sh", "-c", "gunicorn server:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120"]
