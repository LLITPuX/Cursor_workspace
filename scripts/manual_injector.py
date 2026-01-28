#!/usr/bin/env python3
"""
Manual Injector for Session 2026-01-16_diagnosis.
Reads the hardcoded schema plan and injects it into FalkorDB.
"""

import os
import uuid
import json
from datetime import datetime

try:
    from falkordb import FalkorDB
except ImportError:
    print("Error: falkordb not installed.")
    exit(1)

# --- HARDCODED PLAN FROM MANUAL_INGESTION_PLAN.YAML ---
PLAN = {
    "session": {
        "id": "session_2026-01-16_diagnosis",
        "title": "Diagnosing Session Save Issue",
        "date": "2026-01-16",
        "topic": "Diagnosing Neon MCP read-only mode",
        "file_path": "saved_sessions/session_2026-01-16_diagnosis.md"
    },
    "interactions": [
        {
            "id": "interaction_1",
            "role": "user",
            "content": "Что-то не понят ное произошло в прошлой сессии, ты почему-то разучился сохранять сессии... Я хочу разобраться в чем причина...",
            "agent_cycle": {
                "analysis": {
                    "summary": "Initial Diagnosis",
                    "content": "Identified read-only mode in Neon MCP. Deleted unnecessary files."
                },
                "actions": [
                    {
                        "id": "action_delete_files",
                        "type": "FileDelete",
                        "summary": "Delete distraction files",
                        "files": ["TEST_WRITE_ACCESS.md", "FIX_NEON_MCP_READONLY.md", "APPLY_MIGRATION_006.md"]
                    },
                    {
                        "id": "action_propose_solution_1",
                        "type": "Plan",
                        "summary": "Propose checking settings",
                        "content": "Suggested turning off read-only mode in Neon MCP settings in Cursor."
                    }
                ],
                "response": {
                    "content": "Neon MCP is in read-only mode. Solution: Turn it off in Cursor settings."
                }
            }
        },
        {
            "id": "interaction_2",
            "role": "user",
            "content": "несуществует таких настроек. Объясни мне как ты сохранял сесси раньше... Ответь на вопрос, почему раньше такой проблемы небыло.",
            "feedback_on_previous": {
                "target_node_id": "action_propose_solution_1",
                "sentiment": "negative",
                "type": "CRITIQUES",
                "comment": "Settings do not exist. User is frustrated by hallucinations."
            },
            "agent_cycle": {
                "analysis": {
                    "summary": "Deep Dive into History",
                    "content": "Checked past sessions, compute status. Found compute suspended.",
                    "entities": [
                        {"type": "Tool", "name": "Neon Console"}
                    ]
                },
                "actions": [
                    {
                        "id": "action_identify_cause",
                        "type": "Analysis",
                        "summary": "Identify suspended compute",
                        "content": "Found `suspended_at` timestamp. Compute is paused, causing read-only.",
                        "entities": [
                            {"type": "Error", "name": "Compute Suspended"}
                        ]
                    }
                ],
                "response": {
                    "content": "Found the cause: Compute is suspended (Scale to zero: 5 min). This causes read-only."
                }
            }
        },
        {
            "id": "interaction_3",
            "role": "user",
            "content": "я не6 переходил вэтот злоебучий режим read-only. Как егог выключить?",
            "agent_cycle": {
                "response": {
                    "content": "Provided 3 barriers to fix: Resume compute, Disable auto-suspend, Check MCP."
                }
            }
        },
        {
            "id": "interaction_4",
            "role": "user",
            "content": "[Screenshot of Neon Console]",
            "agent_cycle": {
                "analysis": {
                    "summary": "Analyze Screenshot",
                    "content": "Confirmed 'Scale to zero: 5 minutes' in screenshot."
                },
                "response": {
                    "content": "Confirmed 'Scale to zero: 5 minutes' is the culprit. Recommendation: Set to Never."
                }
            }
        },
        {
            "id": "interaction_5",
            "role": "user",
            "content": "Скажи, ты можешь создать документ формата .md в котором будет будет отображена вся эта сессия...?",
            "agent_cycle": {
                "actions": [
                    {
                        "id": "action_offer_manual",
                        "type": "Plan",
                        "summary": "Offer to show content",
                        "content": "Stated I am in ask mode and cannot create files, offered to show content."
                    }
                ],
                "response": {
                    "content": "I can show you the content to save manually."
                }
            }
        },
        {
            "id": "interaction_6",
            "role": "user",
            "content": "Я не просил тебя создавать документ, а прросто спросил можешь ли ты его создать. Но раз ты можешь это сделать, то создай...",
            "feedback_on_previous": {
                "target_node_id": "action_offer_manual",
                "sentiment": "negative",
                "type": "CRITIQUES",
                "comment": "User penalized the misunderstanding/laziness. Agent should have just created it."
            },
            "agent_cycle": {
                "actions": [
                    {
                        "id": "action_create_session_file",
                        "type": "FileWrite",
                        "summary": "Create Session File",
                        "entities": [
                            {"type": "File", "name": "saved_sessions/session_2026-01-16_diagnosis.md"}
                        ],
                        "status": "Success"
                    }
                ],
                "response": {
                    "content": "Created saved_sessions/session_2026-01-16_diagnosis.md"
                }
            }
        }
    ]
}

# --- CONFIG ---
GRAPH_NAME = os.getenv("FALKORDB_GRAPH_NAME", "agent_memory")
HOST = "falkordb" # Internal to docker
PORT = 6379

def get_timestamp():
    return datetime.now().isoformat()

def main():
    print(f"🔌 Connecting to FalkorDB ({HOST}:{PORT})...")
    client = FalkorDB(host=HOST, port=PORT, password=None)
    graph = client.select_graph(GRAPH_NAME)
    
    # 1. Create Session Node
    session_data = PLAN["session"]
    ts = get_timestamp()
    
    print(f"📝 Creating Session: {session_data['title']}")
    graph.query("""
        MERGE (s:Session {id: $id})
        SET s.title = $title,
            s.date = $date,
            s.topic = $topic,
            s.file_path = $file_path,
            s.created_at = $ts
    """, {
        "id": session_data["id"],
        "title": session_data["title"],
        "date": session_data["date"],
        "topic": session_data["topic"],
        "file_path": session_data["file_path"],
        "ts": ts
    })

    prev_interaction_node_id = None
    
    # Map to store action IDs for validation linking
    action_id_map = {}

    for idx, interaction in enumerate(PLAN["interactions"]):
        print(f"  🔹 Processing Interaction {idx + 1}...")
        
        # 2. Create User Query Node (instead of generic Message)
        u_query_id = str(uuid.uuid4())
        graph.query("""
            MATCH (s:Session {id: $session_id})
            CREATE (u:UserQuery {
                id: $id,
                content: $content,
                role: 'user',
                created_at: $ts
            })
            CREATE (s)-[:HAS_EVENT]->(u)
            RETURN u
        """, {
            "session_id": session_data["id"],
            "id": u_query_id,
            "content": interaction["content"],
            "ts": ts
        })

        # Link previous interaction if exists (Chain of thought)
        if prev_interaction_node_id:
            graph.query("""
                MATCH (prev {id: $prev_id}), (curr {id: $curr_id})
                CREATE (prev)-[:NEXT]->(curr)
            """, {
                "prev_id": prev_interaction_node_id,
                "curr_id": u_query_id
            })
            
        prev_interaction_node_id = u_query_id

        # 3. Handle Feedback (Validates/Critiques previous actions)
        if "feedback_on_previous" in interaction:
            fb = interaction["feedback_on_previous"]
            target_logical_id = fb["target_node_id"]
            
            # Find the actual DB ID for this logical ID
            if target_logical_id in action_id_map:
                target_db_id = action_id_map[target_logical_id]
                fb_id = str(uuid.uuid4())
                
                print(f"    📢 Injecting Feedback ({fb['sentiment']}) on {target_logical_id}")
                
                # Determine relationship type
                rel_type = fb.get("type", "CRITIQUES") # VALIDATES or CRITIQUES
                
                graph.query(f"""
                    MATCH (u:UserQuery {{id: $u_id}})
                    MATCH (target {{id: $target_id}})
                    CREATE (f:FeedbackNode {{
                        id: $fb_id,
                        sentiment: $sentiment,
                        comment: $comment,
                        created_at: $ts
                    }})
                    CREATE (u)-[:PROVIDES_FEEDBACK]->(f)
                    CREATE (f)-[:{rel_type}]->(target)
                """, {
                    "u_id": u_query_id,
                    "target_id": target_db_id,
                    "fb_id": fb_id,
                    "sentiment": fb["sentiment"],
                    "comment": fb.get("comment", ""),
                    "ts": ts
                })
            else:
                print(f"    ⚠️ Warning: Feedback target {target_logical_id} not found in map!")

        # 4. Agent Cycle (Analysis -> Plan -> Action -> Response)
        cycle = interaction.get("agent_cycle", {})
        
        # We will chain these: UserQuery -> Analysis -> Plan -> Actions...
        current_step_id = u_query_id
        
        # A. Analysis
        if "analysis" in cycle:
            an = cycle["analysis"]
            an_id = str(uuid.uuid4())
            graph.query("""
                MATCH (prev {id: $prev_id})
                CREATE (a:AnalysisNode {
                    id: $id,
                    summary: $summary,
                    content: $content,
                    created_at: $ts
                })
                CREATE (prev)-[:NEXT]->(a)
            """, {
                "prev_id": current_step_id,
                "id": an_id,
                "summary": an.get("summary", "Analysis"),
                "content": an.get("content", ""),
                "ts": ts
            })
            current_step_id = an_id
            
            # Entities
            for ent in an.get("entities", []):
                graph.query("""
                    MATCH (node {id: $node_id})
                    MERGE (e:Entity {name: $name})
                    ON CREATE SET e.type = $type
                    CREATE (node)-[:MENTIONS]->(e)
                """, {"node_id": an_id, "name": ent["name"], "type": ent["type"]})

        # B. Plan (Optional node if exists, or inside Actions)
        # For simplicity, if structure has 'actions' but no explicit plan text, actions are next.
        # Check if actions exist
        
        if "actions" in cycle:
            for action in cycle["actions"]:
                act_db_id = str(uuid.uuid4())
                # Save mapping for later feedback
                if "id" in action:
                    action_id_map[action["id"]] = act_db_id
                
                print(f"    🎬 Action: {action.get('summary')} ({action.get('type')})")
                
                graph.query("""
                    MATCH (prev {id: $prev_id})
                    CREATE (act:ActionNode {
                        id: $id,
                        type: $type,
                        summary: $summary,
                        content: $content,
                        status: $status,
                        created_at: $ts
                    })
                    CREATE (prev)-[:NEXT]->(act)
                """, {
                    "prev_id": current_step_id,
                    "id": act_db_id,
                    "type": action.get("type", "Generic"),
                    "summary": action.get("summary", ""),
                    "content": action.get("content", ""),
                    "status": action.get("status", "Completed"),
                    "ts": ts
                })
                current_step_id = act_db_id
                
                # Entities
                for ent in action.get("entities", []):
                    graph.query("""
                        MATCH (node {id: $node_id})
                        MERGE (e:Entity {name: $name})
                        ON CREATE SET e.type = $type
                        CREATE (node)-[:MENTIONS]->(e)
                    """, {"node_id": act_db_id, "name": ent["name"], "type": ent["type"]})
                    
        # C. Response
        if "response" in cycle:
            resp = cycle["response"]
            resp_id = str(uuid.uuid4())
            graph.query("""
                MATCH (prev {id: $prev_id})
                CREATE (r:AgentResponse {
                    id: $id,
                    content: $content,
                    created_at: $ts
                })
                CREATE (prev)-[:NEXT]->(r)
            """, {
                "prev_id": current_step_id,
                "id": resp_id,
                "content": resp.get("content", ""),
                "ts": ts
            })
            # Response is the end of this cycle
            prev_interaction_node_id = resp_id

    print("✅ Manual Ingestion Complete!")

if __name__ == "__main__":
    main()
