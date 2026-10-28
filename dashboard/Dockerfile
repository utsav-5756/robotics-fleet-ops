FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[dashboard]"

EXPOSE 8501
CMD ["streamlit", "run", "src/fleet_ops/dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
