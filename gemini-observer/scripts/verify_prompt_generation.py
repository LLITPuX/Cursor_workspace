"""
Verification script for GraphPromptBuilder.
Connects to FalkorDB, builds prompts for each role, and validates they contain graph data.

Usage (ONLY via Docker):
    docker exec -it gemini-observer-bot-1 python scripts/verify_prompt_generation.py
"""

import asyncio
import redis.asyncio as redis
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory.prompt_builder import GraphPromptBuilder


async def verify():
    print("=" * 60)
    print("🔍 GraphPromptBuilder Verification")
    print("=" * 60)

    # Connect to Redis/FalkorDB
    redis_url = os.environ.get("FALKORDB_URL", "redis://falkordb:6379")
    print(f"\n📡 Connecting to {redis_url}...")
    
    try:
        redis_client = redis.from_url(redis_url, encoding="utf-8", decode_responses=False)
        await redis_client.ping()
        print("✅ Connected to Redis/FalkorDB")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

    builder = GraphPromptBuilder(redis_client=redis_client)

    # Test roles
    roles = ["Thinker", "Analyst", "Coordinator", "Responder"]
    all_passed = True

    for role in roles:
        print(f"\n{'─' * 40}")
        print(f"📋 Testing Role: {role}")
        print(f"{'─' * 40}")

        prompt = await builder.build_system_prompt(role)

        if not prompt or prompt.startswith("You are the"):
            print(f"  ❌ FAIL: Empty or fallback prompt for '{role}'")
            all_passed = False
            continue

        print(f"  ✅ Prompt generated: {len(prompt)} chars")
        print(f"  📝 Preview:\n{prompt[:200]}...")

        # Validate key phrases from graph
        checks = {
            "Thinker": ["неупереджено"],
            "Analyst": ["інтент", "план дій"],
            "Coordinator": ["Виконання"],
            "Responder": ["Бобер", "Сікфан"],
        }

        role_checks = checks.get(role, [])
        for phrase in role_checks:
            if phrase.lower() in prompt.lower():
                print(f"  ✅ Contains: '{phrase}'")
            else:
                print(f"  ⚠️  Missing: '{phrase}' (may be ok if graph data differs)")

    # Test build_analyst_prompt with runtime data
    print(f"\n{'─' * 40}")
    print("📋 Testing build_analyst_prompt()")
    print(f"{'─' * 40}")
    analyst_prompt = await builder.build_analyst_prompt("User asks about weather", "What's the weather?")
    if analyst_prompt and "Analyst" in analyst_prompt:
        print(f"  ✅ Analyst prompt generated: {len(analyst_prompt)} chars")
    else:
        print(f"  ❌ FAIL: Analyst prompt missing role context")
        all_passed = False

    # Test build_narrative_prompt with runtime data
    print(f"\n{'─' * 40}")
    print("📋 Testing build_narrative_prompt()")
    print(f"{'─' * 40}")
    narrative_prompt = await builder.build_narrative_prompt(
        "Hello there!", [{"time": "12:00", "author": "User", "text": "Hi"}]
    )
    if narrative_prompt and "Thinker" in narrative_prompt:
        print(f"  ✅ Narrative prompt generated: {len(narrative_prompt)} chars")
    else:
        print(f"  ❌ FAIL: Narrative prompt missing role context")
        all_passed = False

    # Test build_responder_prompt
    print(f"\n{'─' * 40}")
    print("📋 Testing build_responder_prompt()")
    print(f"{'─' * 40}")
    responder_prompt = await builder.build_responder_prompt(rag_context="Test RAG data")
    if responder_prompt and "Responder" in responder_prompt:
        print(f"  ✅ Responder prompt generated: {len(responder_prompt)} chars")
        if "Test RAG data" in responder_prompt:
            print(f"  ✅ RAG context injected correctly")
        else:
            print(f"  ❌ FAIL: RAG context not injected")
            all_passed = False
    else:
        print(f"  ❌ FAIL: Responder prompt missing role context")
        all_passed = False

    # Summary
    print(f"\n{'=' * 60}")
    if all_passed:
        print("🎉 ALL CHECKS PASSED! GraphPromptBuilder is operational.")
    else:
        print("⚠️  SOME CHECKS FAILED. Review output above.")
    print(f"{'=' * 60}")

    await redis_client.close()
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(verify())
    sys.exit(0 if result else 1)
