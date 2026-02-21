FROM python:3.12-slim

# Install Java (required for OWASP Dependency Check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install OWASP Dependency Check
ENV DC_VERSION=10.0.4
RUN wget -q https://github.com/jeremylong/DependencyCheck/releases/download/v${DC_VERSION}/dependency-check-${DC_VERSION}-release.zip \
    -O /tmp/dc.zip \
    && unzip -q /tmp/dc.zip -d /opt/ \
    && rm /tmp/dc.zip \
    && chmod +x /opt/dependency-check/bin/dependency-check.sh

# Create data directory for NVD database
RUN mkdir -p /opt/dependency-check-data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/reports data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
