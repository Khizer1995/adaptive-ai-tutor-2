from core.langgraph_flow import adaptive_graph

# Access internal graph structure safely
graph = adaptive_graph.get_graph()

print("\nNodes:")
for node in graph.nodes:
    print("-", node)

print("\nEdges:")
for edge in graph.edges:
    print(edge)
