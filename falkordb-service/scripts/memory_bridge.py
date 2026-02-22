import sys
import json
from falkordb import FalkorDB

def e_str(value):
    """Екранування рядків для Cypher"""
    if value is None:
        return '""'
    # Заміна подвійних лапок на одинарні, щоб не зламати Cypher 
    # та екранування бекслешів
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'

def main():
    try:
        # Читання JSON з STDIN
        input_data = sys.stdin.read()
        if input_data.startswith('\ufeff'):
            input_data = input_data[1:]
            
        if not input_data.strip():
            print(json.dumps({"status": "error", "message": "No input data provided"}))
            sys.exit(1)
            
        data = json.loads(input_data)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "message": f"Invalid JSON JSONDecodeError: {str(e)}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Error reading input: {str(e)}"}))
        sys.exit(1)

    try:
        # З'єднання з falkordb
        db = FalkorDB(host='falkordb', port=6379)
        graph = db.select_graph('Grynya')
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Redis connection error: {str(e)}"}))
        sys.exit(1)

    queries = []

    # 1. Створення Сесії (якщо є)
    if 'session' in data:
        s = data['session']
        s_id = s.get('id')
        props = ", ".join([f"{k}: {e_str(v)}" for k, v in s.items() if k != 'id'])
        queries.append(f"MERGE (s:Session {{id: '{s_id}'}}) SET s += {{{props}}}")

    # 2. Створення Хронології (Year/Day)
    if 'chronology' in data:
        c = data['chronology']
        day_id = c.get('day_id')
        date_str = c.get('date')
        y_val = c.get('year')
        
        if day_id and date_str and y_val:
            y_id = f"y_{y_val}"
            queries.append(f"MERGE (y:Year {{value: {y_val}, id: '{y_id}', name: '{y_val}'}})")
            queries.append(f"MERGE (d:Day {{date: '{date_str}', id: '{day_id}', name: '{date_str}'}})")
            queries.append(f"MERGE (y)-[:MONTH {{number: {date_str.split('-')[1]}}}]->(d)")

    # 3. Створення Вузлів (Nodes)
    if 'nodes' in data:
        for i, node in enumerate(data['nodes']):
            n_type = node.get('type')
            n_data = node.get('data', {})
            n_id = n_data.get('id')
            
            if not n_type or not n_id:
                continue
                
            props = ", ".join([f"{k}: {e_str(v)}" for k, v in n_data.items() if k != 'id'])
            
            # Створюємо вузол
            queries.append(f"MERGE (n{i}:{n_type} {{id: '{n_id}'}}) SET n{i} += {{{props}}}")
            
            # Прив'язуємо до дня (якщо вказано)
            if 'chronology' in data and data['chronology'].get('time'):
                t = data['chronology']['time']
                day_id = data['chronology'].get('day_id')
                queries.append(f"MATCH (n), (d:Day {{id: '{day_id}'}}) WHERE n.id = '{n_id}' MERGE (n)-[:HAPPENED_AT {{time: '{t}'}}]->(d)")

            # Створюємо зв'язки цього вузла з іншими
            if 'relations' in node:
                for rel in node['relations']:
                    r_type = rel.get('type')
                    target_id = rel.get('target_id')
                    r_props = rel.get('props')
                    
                    if r_type and target_id:
                        if r_props and isinstance(r_props, dict):
                            props_str = ", ".join([f"{k}: {e_str(v)}" for k, v in r_props.items()])
                            queries.append(f"MATCH (source), (target) WHERE source.id = '{n_id}' AND target.id = '{target_id}' MERGE (source)-[r:{r_type}]->(target) SET r += {{{props_str}}}")
                        else:
                            queries.append(f"MATCH (source), (target) WHERE source.id = '{n_id}' AND target.id = '{target_id}' MERGE (source)-[:{r_type}]->(target)")

    # 4. Хронологія NEXT
    if 'chronology' in data and data['chronology'].get('next_links'):
        for link in data['chronology']['next_links']:
            source_id = link.get('source_id')
            target_id = link.get('target_id')
            if source_id and target_id:
                queries.append(f"MATCH (source), (target) WHERE source.id = '{source_id}' AND target.id = '{target_id}' MERGE (source)-[:NEXT]->(target)")

    # 5. Останній івент в сесії LAST_EVENT
    if 'chronology' in data and data['chronology'].get('last_event_id') and 'session' in data:
        s_id = data['session'].get('id')
        last_id = data['chronology']['last_event_id']
        queries.append(f"MATCH (s:Session {{id: '{s_id}'}})-[rel:LAST_EVENT]->() DELETE rel")
        queries.append(f"MATCH (s:Session {{id: '{s_id}'}}), (last) WHERE last.id = '{last_id}' MERGE (s)-[:LAST_EVENT]->(last)")


    # Виконання всіх Query
    results = []
    try:
        # Для FalKorDB краще робити один великий запит, або послідовні з гарантованим виконанням
        for q in queries:
            try:
                graph.query(q)
                results.append({"query": q, "status": "success"})
            except Exception as e:
                # Зупиняємо або логуємо помилку
                results.append({"query": q, "status": "error", "message": str(e)})
                
        print(json.dumps({"status": "success", "results": results}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Query execution error: {str(e)}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
