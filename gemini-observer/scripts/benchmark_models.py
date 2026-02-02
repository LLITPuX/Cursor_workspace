import asyncio
import aiohttp
import time
import json
import os
from datetime import datetime

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://falkordb-ollama:11434")
MODELS = [
    "gemma3:4b",
    # "mistral",
    # "gemma2:9b", # Too heavy causing OOM
]

# Prompts
LOGIC_PROMPT = """
You are a data extraction agent. Extract the following information into a strict JSON object:
Name: John Doe
Age: 30
Occupation: Software Engineer
Interest: AI, Basketball
Format: {"name": str, "age": int, "occupation": str, "interests": list}
"""

SPEED_PROMPT = """
Write a short story about a robot who learns to dream (approx 200 words).
"""

async def check_model_availability(session, model):
    try:
        async with session.post(f"{OLLAMA_HOST}/api/show", json={"name": model}) as resp:
            if resp.status == 200:
                return True
            return False
    except Exception as e:
        print(f"Error checking model {model}: {e}")
        return False

async def pull_model(session, model):
    print(f"Pulling {model}... (this might take time)")
    async with session.post(f"{OLLAMA_HOST}/api/pull", json={"name": model}) as resp:
        if resp.status == 200:
            print(f"Model {model} pull started/completed.")
            # Simple wait for completion not implemented here, assuming it's done or fast
            # In detailed script we should read stream
            async for line in resp.content:
                pass # Consume stream to wait
            return True
        return False

async def benchmark_model(session, model):
    print(f"--- Benchmarking {model} ---")
    results = {
        "model": model,
        "ttft": 0,
        "total_speed": 0,
        "logic_pass": False,
        "error": None
    }

    # 1. Warmup / Check needed?
    # We proceed directly.

    # 2. Logic Test (JSON)
    start_time = time.time()
    try:
        async with session.post(f"{OLLAMA_HOST}/api/generate", json={
            "model": model, 
            "prompt": LOGIC_PROMPT, 
            "stream": False,
            "format": "json"
        }) as resp:
            data = await resp.json()
            total_time = time.time() - start_time
            
            response_text = data.get("response", "")
            try:
                json_obj = json.loads(response_text)
                if "name" in json_obj and "age" in json_obj:
                    results["logic_pass"] = True
            except:
                results["logic_pass"] = False
            
            # TTFT is hard to measure without streaming, but total time for small JSON is proxy
            # For speed test we use streaming or eval metrics from ollama if available
            # Ollama returns "eval_count" and "eval_duration" in final response
            
            # Using speed metrics from this response for logic? No, let's look at the speed test.
            
    except Exception as e:
        results["error"] = str(e)
        return results

    # 3. Speed Test (Story)
    try:
        async with session.post(f"{OLLAMA_HOST}/api/generate", json={
            "model": model, 
            "prompt": SPEED_PROMPT, 
            "stream": False
        }) as resp:
            data = await resp.json()
            
            eval_count = data.get("eval_count", 0)
            eval_duration = data.get("eval_duration", 1) # nanoseconds
            
            # Calculate tokens per second
            if eval_duration > 0:
                results["total_speed"] = eval_count / (eval_duration / 1e9)
            
            # Approx TTFT from prompt_eval_duration? 
            # Ollama provides prompt_eval_duration (ns)
            prompt_eval_duration = data.get("prompt_eval_duration", 0)
            if prompt_eval_duration > 0:
                 results["ttft"] = prompt_eval_duration / 1e6 # ms
            
    except Exception as e:
        results["error"] = str(e)

    return results

async def main():
    timeout = aiohttp.ClientTimeout(total=3600) # 1 hour timeout for large pulls
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Check connection
        try:
            async with session.get(f"{OLLAMA_HOST}/") as resp:
                print(f"Ollama connected at {OLLAMA_HOST}")
        except Exception as e:
            print(f"Failed to connect to Ollama at {OLLAMA_HOST}: {e}")
            return

        report_lines = []
        report_lines.append(f"# Model Benchmark Report")
        report_lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"**Host:** {OLLAMA_HOST}")
        report_lines.append("")
        report_lines.append("| Model | TTFT (ms) | Speed (tok/s) | Logic (JSON) | Status |")
        report_lines.append("|---|---|---|---|---|")

        best_model = None
        best_speed = 0

        for model in MODELS:
            print(f"\nChecking model: {model}")
            available = await check_model_availability(session, model)
            if not available:
                print(f"Model {model} not found. Initiating pull...")
                success = await pull_model(session, model)
                if not success:
                    print(f"Failed to pull {model}. Skipping.")
                    continue
            
            # Wait a bit after pull
            # time.sleep(2) 
            
            res = await benchmark_model(session, model)
            
            status = "✅ OK" if res["error"] is None else f"❌ {res['error']}"
            logic = "✅ PASS" if res["logic_pass"] else "❌ FAIL"
            
            line = f"| {res['model']} | {res['ttft']:.2f} | {res['total_speed']:.2f} | {logic} | {status} |"
            report_lines.append(line)
            
            if res["total_speed"] > best_speed and res["logic_pass"]:
                 best_speed = res["total_speed"]
                 best_model = res["model"]

        report_lines.append("")
        report_lines.append(f"**Recommendation:** {best_model if best_model else 'None'}")
        
        report_content = "\n".join(report_lines)
        print("\n" + report_content)
        
        # Save report
        filename = f"reports/model_benchmark_{datetime.now().strftime('%Y-%m-%d')}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"Report saved to {filename}")

if __name__ == "__main__":
    asyncio.run(main())
