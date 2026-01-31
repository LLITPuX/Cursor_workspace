FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Grant execution permissions
RUN chmod +x start.sh

# Expose port for OAuth callback
EXPOSE 8080

CMD ["./start.sh"]
