FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY src ./src
COPY simulator/ros_ws/src/fleet_simulator/fleet_simulator ./simulator/ros_ws/src/fleet_simulator/fleet_simulator
COPY tests ./tests

RUN pip install --no-cache-dir ".[api,test]"

CMD ["python", "-m", "pytest", "-q"]