---
description: How to save a Gemini session from a public URL to the local filesystem
---

# Save Gemini Session Workflow

This workflow describes how to save a Gemini chat session to `saved_sessions/Gemini_chat` using the Docker-based `docs-scraper-service`.

## Prerequisites
- Docker Desktop must be running.
- `docs-scraper-service` container must be running (port 8002).

## Steps to Run

1.  **Ensure Service is Running**:
    ```bash
    cd "c:\Cursor workspace\docs-scraper-service"
    docker-compose up -d --build
    ```

2.  **Execute Scrape Request**:
    Send a POST request to the service with the session URL.

    **Option A: Using curl (PowerShell)**
    ```powershell
    $body = @{
        url = "YOUR_GEMINI_SHARE_URL"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "http://localhost:8002/api/v1/scraper/gemini" -Method Post -Body $body -ContentType "application/json"
    ```

    **Option B: Using curl (CMD/Bash)**
    ```bash
    curl -X POST "http://localhost:8002/api/v1/scraper/gemini" -H "Content-Type: application/json" -d "{\"url\": \"YOUR_GEMINI_SHARE_URL\"}"
    ```

## Output
The file will be saved to `c:\Cursor workspace\saved_sessions\Gemini_chat\` with the following format:
- Filename: `gemini_session_YYYY-MM-DD_Title.md`
- Content: Markdown with timestamp, topic, user queries, and model responses.
