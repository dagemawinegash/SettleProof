FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY settleproof ./settleproof
COPY fixtures ./fixtures
COPY public-demo ./public-demo
RUN pip install --no-cache-dir '.[web]' && useradd --create-home app && mkdir /app/runtime && chown app:app /app/runtime
USER app
EXPOSE 8000
CMD ["uvicorn", "settleproof.hosted:create_hosted_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
