import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from config.settings import settings
from memory.falkordb import FalkorDBProvider

async def verify_graph():
    print("🔌 Connecting to FalkorDB...")
    db = FalkorDBProvider()
    
    try:
        # Check Roles
        print("\n🔍 Checking ROLES:")
        roles_query = "MATCH (r:Role) RETURN r.name, r.description"
        roles_res = await db.query(roles_query)
        
        found_roles = []
        if roles_res and roles_res.result_set:
            for record in roles_res.result_set:
                role_name = record[0]
                desc = record[1]
                print(f"  ✅ Found Role: {role_name}")
                # print(f"     Desc: {desc[:50]}...")
                found_roles.append(role_name)
        else:
            print("  ❌ No Roles found!")

        expected_roles = ["Thinker", "Analyst", "Coordinator", "Responder"]
        for role in expected_roles:
            if role not in found_roles:
                print(f"  ⚠️  MISSING ROLE: {role}")

        # Check Instructions
        print("\n🔍 Checking INSTRUCTIONS:")
        instr_query = "MATCH (r:Role)-[:HAS_INSTRUCTION]->(i:Instruction) RETURN r.name, i.content"
        instr_res = await db.query(instr_query)
        
        if instr_res and instr_res.result_set:
            count = len(instr_res.result_set)
            print(f"  ✅ Found {count} linked instructions.")
            for record in instr_res.result_set:
                print(f"    - [{record[0]}]: {record[1][:50]}...")
        else:
            print("  ❌ No linked Instructions found!")

        # Check Tasks
        print("\n🔍 Checking TASKS:")
        task_query = "MATCH (r:Role)-[:RESPONSIBLE_FOR]->(t:Task) RETURN r.name, t.description"
        task_res = await db.query(task_query)
        
        if task_res and task_res.result_set:
            count = len(task_res.result_set)
            print(f"  ✅ Found {count} linked tasks.")
            for record in task_res.result_set:
                print(f"    - [{record[0]}]: {record[1][:50]}...")
        else:
            print("  ❌ No linked Tasks found!")

    except Exception as e:
        print(f"❌ Error verifying graph: {e}")
    finally:
        # DB provider might not need explicit close if it uses connection pool, 
        # but just in case of lingering sessions
        pass

if __name__ == "__main__":
    asyncio.run(verify_graph())
