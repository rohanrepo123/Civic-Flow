FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY packages ./packages
COPY browser_worker ./browser_worker
RUN pip install --no-cache-dir '.[browser]'
RUN python -m playwright install --with-deps chromium
EXPOSE 8001
CMD ["uvicorn", "browser_worker.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
