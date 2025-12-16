# PowerShell script to generate embeddings
$ollamaUrl = "http://localhost:11434/api/embeddings"
$model = "embeddinggemma:latest"

# Get messages without embeddings from Neon
# This would require Neon connection, so better to use Python script

Write-Host "Please run: python embedding-service\scripts\generate_embeddings_for_all_sessions.py"
Write-Host "Or restart the FastAPI server and call: POST /api/v1/sessions/generate-embeddings/all"

