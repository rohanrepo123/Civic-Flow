FROM python:3.12-slim
WORKDIR /srv
COPY contracts /srv/contracts
COPY services/core_api /srv/core_api
RUN pip install --no-cache-dir -e /srv/contracts/civicflow_contracts -e /srv/core_api
WORKDIR /srv/core_api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
