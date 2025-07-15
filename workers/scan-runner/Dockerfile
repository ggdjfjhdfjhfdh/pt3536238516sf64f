FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY workers/scan-runner/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY workers/scan-runner/run_scan.py run_scan.py

# Command to run the application
CMD ["python", "run_scan.py"]
