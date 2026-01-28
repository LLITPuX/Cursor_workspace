
import os
from falkordb import FalkorDB

HOST = "falkordb"
PORT = 6379
GRAPH_NAME = os.getenv("FALKORDB_GRAPH_NAME", "agent_memory")

def main():
    print(f"🔌 Connecting to FalkorDB ({HOST}:{PORT})...")
    client = FalkorDB(host=HOST, port=PORT, password=None)
    graph = client.select_graph(GRAPH_NAME)
    
    print(f"🗑️ Clearing graph '{GRAPH_NAME}'...")
    
    # Delete all nodes and relationships
    graph.query("MATCH (n) DETACH DELETE n")
    
    # Verify
    res = graph.query("MATCH (n) RETURN count(n)")
    count = res.result_set[0][0]
    
    if count == 0:
        print("✅ Graph is completely empty.")
    else:
        print(f"❌ Warning: Graph still has {count} nodes.")

if __name__ == "__main__":
    main()
