FROM python:3.12-slim
WORKDIR /srv
COPY contracts /srv/contracts
COPY services/browser_agent /srv/browser_agent
RUN pip install --no-cache-dir -e /srv/contracts/civicflow_contracts -e /srv/browser_agent && playwright install --with-deps chromium
WORKDIR /srv/browser_agent
EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
