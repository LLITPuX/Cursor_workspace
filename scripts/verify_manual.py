import os
from falkordb import FalkorDB

HOST = "falkordb"
PORT = 6379
GRAPH_NAME = os.getenv("FALKORDB_GRAPH_NAME", "agent_memory")

def main():
    print(f"🔌 Connecting to FalkorDB ({HOST}:{PORT})...")
    client = FalkorDB(host=HOST, port=PORT, password=None)
    graph = client.select_graph(GRAPH_NAME)
    
    print("\n🔍 Checking for Feedback Nodes...")
    res = graph.query("""
        MATCH (u:UserQuery)-[:PROVIDES_FEEDBACK]->(f:FeedbackNode)-[rel]->(target)
        RETURN u.content, f.sentiment, f.comment, type(rel), labels(target), target.summary
    """)
    
    for row in res.result_set:
        u_content = row[0][:50] + "..."
        sentiment = row[1]
        comment = row[2]
        rel_type = row[3]
        target_label = row[4]
        target_summary = row[5]
        
        print(f"\nUser Query: '{u_content}'")
        print(f"  └── Feedback ({sentiment}): \"{comment}\"")
        print(f"      └── [{rel_type}] ──> ({target_label}): {target_summary}")

    print("\n🔍 Checking Session Summary...")
    res = graph.query("""
        MATCH (s:Session {id: 'session_2026-01-16_diagnosis'})
        RETURN s.title, s.topic
    """)
    print(f"Session: {res.result_set[0][0]} ({res.result_set[0][1]})")

if __name__ == "__main__":
    main()
