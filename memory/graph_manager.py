"""
memory/graph_manager.py — Dynamic Knowledge Graph Manager for Graphify

Manages dynamic mutation and decay of entities in the graphify-out/ knowledge graph.
"""

import json
import os
import time
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
import shutil

# Try to import networkx for efficient graph operations
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    # We'll fallback to using JSON directly

# Constants
GRAPH_ROOT = Path("graphify-out")
GRAPH_JSON = GRAPH_ROOT / "graph.json"
# Decay rate (per hour) - can be adjusted
DEFAULT_DECAY_RATE = 0.1  # Adjust as needed
# Weight threshold below which nodes are purged
WEIGHT_THRESHOLD = 0.15
# Initial weight for new temporary nodes
DEFAULT_INITIAL_WEIGHT = 1.0


class GraphManager:
    """
    Manages the knowledge graph stored in graphify-out/.
    Supports adding nodes/relationships, applying decay, and querying.
    """

    def __init__(self, graph_path: Optional[Path] = None):
        """
        Initialize the GraphManager.
        If graph_path is None, uses graphify-out/graph.json.
        """
        self.graph_path = graph_path or GRAPH_JSON
        self._ensure_graph_exists()
        self._load_graph()

    def _ensure_graph_exists(self):
        """Ensure the graph file exists; if not, create an empty one."""
        if not self.graph_path.exists():
            self.graph_path.parent.mkdir(parents=True, exist_ok=True)
            # Create an empty graph structure
            empty_graph = {
                "directed": False,
                "multigraph": False,
                "graph": {},
                "nodes": [],
                "edges": []
            }
            self._save_graph(empty_graph)

    def _load_graph(self):
        """Load the graph from the JSON file."""
        try:
            with open(self.graph_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading graph from {self.graph_path}: {e}")
            # Initialize empty graph
            data = {
                "directed": False,
                "multigraph": False,
                "graph": {},
                "nodes": [],
                "edges": []
            }

        if NETWORKX_AVAILABLE:
            # Convert to networkx graph for easier manipulation
            self._nx_graph = nx.Graph() if not data.get("directed", False) else nx.DiGraph()
            # Add nodes with attributes
            for node in data.get("nodes", []):
                node_id = node["id"]
                # Remove id from attributes to avoid conflict
                attrs = {k: v for k, v in node.items() if k != "id"}
                self._nx_graph.add_node(node_id, **attrs)
            # Add edges
            for edge in data.get("edges", []):
                # Assuming edges are in format: [source, target, attributes] or [source, target]
                if len(edge) >= 2:
                    source, target = edge[0], edge[1]
                    attrs = edge[2] if len(edge) > 2 else {}
                    self._nx_graph.add_edge(source, target, **attrs)
        else:
            # Store raw data
            self._data = data

    def _save_graph(self, data: Optional[Dict] = None):
        """Save the graph data to the JSON file atomically."""
        if data is None:
            if NETWORKX_AVAILABLE:
                # Convert networkx graph to dict
                data = {
                    "directed": self._nx_graph.directed,
                    "multigraph": self._nx_graph.multigraph,
                    "graph": self._nx_graph.graph,
                    "nodes": [
                        {"id": node, **attrs}
                        for node, attrs in self._nx_graph.nodes(data=True)
                    ],
                    "edges": [
                        [u, v, attrs]
                        for u, v, attrs in self._nx_graph.edges(data=True)
                    ]
                }
            else:
                data = self._data

        # Write to temporary file first, then rename for atomicity
        temp_file = self.graph_path.with_suffix('.json.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Replace the original file
            shutil.move(str(temp_file), str(self.graph_path))
        except Exception as e:
            print(f"Error saving graph to {self.graph_path}: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def add_entity_node(self, entity_name: str, category: str = "entity",
                       attributes: Optional[Dict] = None,
                       is_temporary: bool = True,
                       initial_weight: float = DEFAULT_INITIAL_WEIGHT) -> bool:
        """
        Add an entity node to the graph.
        Returns True if successful.
        """
        attrs = attributes or {}
        # Add standard attributes for decay and categorization
        attrs.update({
            "category": category,
            "is_temporary": is_temporary,
            "weight": initial_weight,
            "initial_weight": initial_weight,
            "timestamp": time.time(),
            "added_by": "graph_manager"
        })

        if NETWORKX_AVAILABLE:
            # Check if node already exists
            if self._nx_graph.has_node(entity_name):
                # Update attributes? We'll merge or overwrite? We'll update weight and timestamp if temporary?
                # For simplicity, we'll not add duplicate; we'll update the existing node's attributes.
                # But we want to allow updating weight? We'll just return False if exists.
                # Alternatively, we could update the weight and timestamp.
                # Let's decide: if exists and is_temporary, we refresh the weight and timestamp.
                # If permanent, we might not want to change weight.
                existing = self._nx_graph.nodes[entity_name]
                if existing.get("is_temporary", False) and is_temporary:
                    # Refresh the weight and timestamp
                    existing["weight"] = initial_weight
                    existing["timestamp"] = time.time()
                    # Update other attributes
                    for k, v in attrs.items():
                        existing[k] = v
                    self._save_graph()
                    return True
                else:
                    # Node exists and is permanent or we don't want to overwrite
                    return False
            else:
                self._nx_graph.add_node(entity_name, **attrs)
                self._save_graph()
                return True
        else:
            # Fallback to JSON
            # Check if node already exists
            for node in self._data["nodes"]:
                if node["id"] == entity_name:
                    # Update attributes
                    node.update(attrs)
                    self._save_graph()
                    return True
            # Add new node
            new_node = {"id": entity_name, **attrs}
            self._data["nodes"].append(new_node)
            self._save_graph()
            return True

    def add_relationship(self, source: str, target: str, relation_type: str = "related",
                        attributes: Optional[Dict] = None) -> bool:
        """
        Add a relationship (edge) between two nodes.
        Returns True if successful.
        """
        attrs = attributes or {}
        attrs.update({
            "relation_type": relation_type,
            "added_by": "graph_manager",
            "timestamp": time.time()
        })

        if NETWORKX_AVAILABLE:
            # Ensure both nodes exist
            if not self._nx_graph.has_node(source):
                # Optionally create the source node? We'll require nodes to exist first.
                return False
            if not self._nx_graph.has_node(target):
                return False
            self._nx_graph.add_edge(source, target, **attrs)
            self._save_graph()
            return True
        else:
            # Fallback to JSON
            # Check if nodes exist
            source_exists = any(node["id"] == source for node in self._data["nodes"])
            target_exists = any(node["id"] == target for node in self._data["nodes"])
            if not (source_exists and target_exists):
                return False
            # Add edge
            edge = [source, target, attrs]
            self._data["edges"].append(edge)
            self._save_graph()
            return True

    def apply_decay(self, decay_rate: float = DEFAULT_DECAY_RATE) -> int:
        """
        Apply exponential decay to all temporary nodes.
        Returns the number of nodes purged.
        """
        current_time = time.time()
        purged_count = 0
        nodes_to_purge = []

        if NETWORKX_AVAILABLE:
            for node_id, attrs in self._nx_graph.nodes(data=True):
                if attrs.get("is_temporary", False):
                    initial_weight = attrs.get("initial_weight", DEFAULT_INITIAL_WEIGHT)
                    timestamp = attrs.get("timestamp", current_time)
                    elapsed_hours = (current_time - timestamp) / 3600.0
                    weight = initial_weight * math.exp(-decay_rate * elapsed_hours)
                    attrs["weight"] = weight
                    if weight < WEIGHT_THRESHOLD:
                        nodes_to_purge.append(node_id)
            # Purge nodes
            for node_id in nodes_to_purge:
                self._nx_graph.remove_node(node_id)
                purged_count += 1
            if purged_count > 0:
                self._save_graph()
        else:
            # Fallback to JSON
            new_nodes = []
            for node in self._data["nodes"]:
                if node.get("is_temporary", False):
                    initial_weight = node.get("initial_weight", DEFAULT_INITIAL_WEIGHT)
                    timestamp = node.get("timestamp", current_time)
                    elapsed_hours = (current_time - timestamp) / 3600.0
                    weight = initial_weight * math.exp(-decay_rate * elapsed_hours)
                    node["weight"] = weight
                    if weight >= WEIGHT_THRESHOLD:
                        new_nodes.append(node)
                    else:
                        purged_count += 1
                else:
                    new_nodes.append(node)
            self._data["nodes"] = new_nodes
            if purged_count > 0:
                self._save_graph()

        return purged_count

    def query_knowledge_graph(self, concept: str, max_hops: int = 2) -> Dict[str, Any]:
        """
        Query the knowledge graph for a concept and return connected subgraph up to max_hops deep.
        Returns a dictionary with nodes and edges of the subgraph.
        """
        if NETWORKX_AVAILABLE:
            if not self._nx_graph.has_node(concept):
                return {"nodes": [], "edges": []}

            # Get nodes within max_hops
            if self._nx_graph.directed:
                # For directed graph, we need to consider successors and predecessors?
                # We'll treat as undirected for simplicity in query, or we can do BFS following edge direction.
                # Let's do BFS following outgoing edges only (as per typical query).
                # We'll use nx.single_source_shortest_path_length with cutoff.
                try:
                    path_lengths = nx.single_source_shortest_path_length(
                        self._nx_graph, concept, cutoff=max_hops
                    )
                except nx.NodeNotFound:
                    return {"nodes": [], "edges": []}
            else:
                # Undirected graph
                try:
                    path_lengths = nx.single_source_shortest_path_length(
                        self._nx_graph, concept, cutoff=max_hops
                    )
                except nx.NodeNotFound:
                    return {"nodes": [], "edges": []}

            # Get the subgraph
            nodes_in_subgraph = list(path_lengths.keys())
            subgraph = self._nx_graph.subgraph(nodes_in_subgraph)

            # Convert to dict format
            result = {
                "nodes": [
                    {"id": node, **attrs}
                    for node, attrs in subgraph.nodes(data=True)
                ],
                "edges": [
                    [u, v, attrs]
                    for u, v, attrs in subgraph.edges(data=True)
                ]
            }
            return result
        else:
            # Fallback: simple implementation - just return the node and its direct neighbors
            # This is limited but works for small graphs.
            # Find the node
            node_data = None
            for node in self._data["nodes"]:
                if node["id"] == concept:
                    node_data = node
                    break
            if not node_data:
                return {"nodes": [], "edges": []}

            # Collect nodes within max_hops (we'll do BFS manually)
            visited = set()
            frontier = [concept]
            visited.add(concept)
            # We'll store edges as we go
            edges_found = []
            # We need to map node id to index for quick lookup
            node_id_to_index = {node["id"]: i for i, node in enumerate(self._data["nodes"])}

            for hop in range(max_hops):
                next_frontier = []
                for node_id in frontier:
                    # Find edges where this node is source or target
                    for edge in self._data["edges"]:
                        source, target = edge[0], edge[1]
                        attrs = edge[2] if len(edge) > 2 else {}
                        if source == node_id and target not in visited:
                            visited.add(target)
                            next_frontier.append(target)
                            edges_found.append([source, target, attrs])
                        elif target == node_id and source not in visited:
                            visited.add(source)
                            next_frontier.append(source)
                            edges_found.append([target, source, attrs])  # reverse?
                frontier = next_frontier
                if not frontier:
                    break

            # Collect all visited nodes
            visited_nodes = []
            for node_id in visited:
                idx = node_id_to_index.get(node_id)
                if idx is not None:
                    visited_nodes.append(self._data["nodes"][idx])

            return {
                "nodes": visited_nodes,
                "edges": edges_found
            }

    def get_permanent_nodes(self) -> List[Dict]:
        """Return all nodes marked as permanent (not temporary)."""
        if NETWORKX_AVAILABLE:
            return [
                {"id": node, **attrs}
                for node, attrs in self._nx_graph.nodes(data=True)
                if not attrs.get("is_temporary", False)
            ]
        else:
            return [
                node for node in self._data["nodes"]
                if not node.get("is_temporary", False)
            ]

    def get_temporary_nodes(self) -> List[Dict]:
        """Return all nodes marked as temporary."""
        if NETWORKX_AVAILABLE:
            return [
                {"id": node, **attrs}
                for node, attrs in self._nx_graph.nodes(data=True)
                if attrs.get("is_temporary", False)
            ]
        else:
            return [
                node for node in self._data["nodes"]
                if node.get("is_temporary", False)
            ]


# Example usage and testing
if __name__ == "__main__":
    # Initialize the graph manager
    gm = GraphManager()

    # Add a temporary node
    gm.add_entity_node("task_debug", "temp", {"description": "A debug task"}, is_temporary=True)

    # Add a relationship
    gm.add_relationship("task_debug", "core_gemini_reply", "related_to")

    # Apply decay (should not purge immediately)
    purged = gm.apply_decay()
    print(f"Purged {purged} nodes after decay")

    # Query the graph
    result = gm.query_knowledge_graph("task_debug", max_hops=2)
    print(f"Query result: {len(result['nodes'])} nodes, {len(result['edges'])} edges")