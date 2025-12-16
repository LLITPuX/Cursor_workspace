#!/bin/bash
# Script to initialize Ollama with EmbeddingGemma model
# Usage: docker exec embedding-ollama bash < scripts/init-ollama.sh

echo "Initializing Ollama with EmbeddingGemma model..."

# Pull the model
ollama pull embeddinggemma:latest

# Verify installation
echo "Installed models:"
ollama list

echo "Done! EmbeddingGemma model is ready."

