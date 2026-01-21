#!/usr/bin/env python3
"""Test script for embedding service"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.embedding import EmbeddingService
from app.config import settings
import httpx


async def test_single_embedding():
    """Test single embedding generation"""
    print("=" * 60)
    print("Test 1: Single embedding generation")
    print("=" * 60)
    
    service = EmbeddingService()
    
    test_text = "Test embedding generation for FalkorDB"
    print(f"Text: {test_text}")
    
    try:
        embedding = await service.generate_embedding(test_text)
        print(f"✅ Success: Generated embedding")
        print(f"   Dimension: {len(embedding)} (expected: {service.dimension})")
        print(f"   First 5 values: {embedding[:5]}")
        
        if len(embedding) == service.dimension:
            print(f"   ✅ Dimension matches expected value")
        else:
            print(f"   ❌ Dimension mismatch!")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_batch_embeddings():
    """Test batch embedding generation"""
    print("\n" + "=" * 60)
    print("Test 2: Batch embedding generation")
    print("=" * 60)
    
    service = EmbeddingService()
    
    test_texts = [
        "FalkorDB is a graph database",
        "Python is a programming language",
        "FastAPI is a web framework",
        "Ollama provides embeddings",
        "Docker containers are useful"
    ]
    
    print(f"Texts to embed: {len(test_texts)}")
    for i, text in enumerate(test_texts, 1):
        print(f"  {i}. {text}")
    
    try:
        import time
        start_time = time.time()
        embeddings = await service.generate_embeddings_batch(test_texts)
        elapsed_time = time.time() - start_time
        
        print(f"\n✅ Success: Generated {len(embeddings)} embeddings")
        print(f"   Time: {elapsed_time:.2f} seconds")
        print(f"   Average time per embedding: {elapsed_time/len(embeddings):.2f} seconds")
        
        # Check dimensions
        all_correct = True
        for i, emb in enumerate(embeddings):
            if len(emb) != service.dimension:
                print(f"   ❌ Embedding {i+1}: dimension mismatch ({len(emb)} != {service.dimension})")
                all_correct = False
            else:
                print(f"   ✅ Embedding {i+1}: dimension correct ({len(emb)})")
        
        return all_correct
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_health_check():
    """Test health check"""
    print("\n" + "=" * 60)
    print("Test 3: Health check")
    print("=" * 60)
    
    service = EmbeddingService()
    
    try:
        is_healthy = await service.health_check()
        
        if is_healthy:
            print(f"✅ Health check passed")
            print(f"   Model: {service.model}")
            print(f"   Dimension: {service.dimension}")
            print(f"   Base URL: {service.base_url}")
        else:
            print(f"❌ Health check failed")
            print(f"   Check if Ollama is running and model '{service.model}' is loaded")
            print(f"   Run: docker exec -it falkordb-ollama ollama pull {service.model}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_empty_text():
    """Test error handling for empty text"""
    print("\n" + "=" * 60)
    print("Test 4: Error handling (empty text)")
    print("=" * 60)
    
    service = EmbeddingService()
    
    try:
        await service.generate_embedding("")
        print("❌ Should have raised ValueError for empty text")
        return False
    except ValueError as e:
        print(f"✅ Correctly raised ValueError: {e}")
        return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


async def test_ollama_connection():
    """Test direct Ollama connection"""
    print("\n" + "=" * 60)
    print("Test 5: Direct Ollama connection check")
    print("=" * 60)
    
    service = EmbeddingService()
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check Ollama availability
            response = await client.get(f"{service.base_url}/api/tags")
            
            if response.status_code == 200:
                print(f"✅ Ollama is accessible at {service.base_url}")
                
                # Check models
                data = response.json()
                models = data.get("models", [])
                model_names = [model.get("name", "") for model in models]
                
                print(f"   Available models: {len(model_names)}")
                for model_name in model_names:
                    marker = "✅" if model_name == service.model else "  "
                    print(f"   {marker} {model_name}")
                
                if service.model in model_names:
                    print(f"\n✅ Required model '{service.model}' is loaded")
                    return True
                else:
                    print(f"\n❌ Required model '{service.model}' is NOT loaded")
                    print(f"   Run: docker exec -it falkordb-ollama ollama pull {service.model}")
                    return False
            else:
                print(f"❌ Ollama returned status {response.status_code}")
                return False
    except httpx.ConnectError:
        print(f"❌ Cannot connect to Ollama at {service.base_url}")
        print(f"   Check if Ollama container is running: docker-compose ps")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Embedding Service Test Suite")
    print("=" * 60)
    print(f"Model: {settings.ollama_model}")
    print(f"Dimension: {settings.embedding_dimension}")
    print(f"Base URL: {settings.ollama_base_url}")
    print("=" * 60)
    
    results = []
    
    # Test 0: Ollama connection
    results.append(await test_ollama_connection())
    
    # Test 1: Health check
    results.append(await test_health_check())
    
    # Test 2: Single embedding
    results.append(await test_single_embedding())
    
    # Test 3: Batch embeddings
    results.append(await test_batch_embeddings())
    
    # Test 4: Error handling
    results.append(await test_empty_text())
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
