# HireOps in a container. The AI model runs in its own container (see docker-compose.yml).
FROM python:3.12-slim
WORKDIR /app
# Install libraries first, so Docker can reuse this layer when only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Never run as root inside a container
RUN useradd --create-home hireops && chown -R hireops /app
USER hireops
ENTRYPOINT ["python", "jd_decoder.py"]
CMD ["--help"]
