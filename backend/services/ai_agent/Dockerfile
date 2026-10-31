FROM python:3.12-slim
WORKDIR /srv
COPY contracts /srv/contracts
COPY services/ai_agent /srv/ai_agent
COPY app/agent /srv/backend/app/agent
RUN pip install --no-cache-dir -e /srv/contracts/civicflow_contracts -e /srv/ai_agent
ENV PYTHONPATH=/srv
WORKDIR /srv/ai_agent
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
