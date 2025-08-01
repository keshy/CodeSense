from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from sentence_transformers import SentenceTransformer
import json
import logging
from typing import Dict, List, Any, Optional
import hashlib

logger = logging.getLogger(__name__)


class GraphSink(object):

    def __init__(self, graph, es_host='localhost', es_port=9200, es_user=None, es_password=None,
                 embedding_model='all-MiniLM-L6-v2'):
        """
        Initialize GraphSink with Elasticsearch connection and embedding model.

        Args:
            graph: The graph object to be stored
            es_host: Elasticsearch host (default: localhost)
            es_port: Elasticsearch port (default: 9200)
            es_user: Username for ES authentication (optional)
            es_password: Password for ES authentication (optional)
            embedding_model: SentenceTransformer model name for embeddings
        """
        self.graph = graph

        # Configure Elasticsearch connection
        es_config = {
            'hosts': [{'host': es_host, 'port': es_port}],
            'timeout': 30,
            'max_retries': 3,
            'retry_on_timeout': True
        }

        if es_user and es_password:
            es_config['http_auth'] = (es_user, es_password)

        self.es = Elasticsearch(**es_config)

        # Initialize embedding model
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()

        # Index names
        self.nodes_index = "graph_nodes"
        self.edges_index = "graph_edges"

        # Ensure indices exist
        self._create_indices()

    def _create_indices(self):
        """Create Elasticsearch indices for nodes and edges with embedding support."""

        # Node index mapping with dense vector for embeddings
        nodes_mapping = {
            "mappings": {
                "properties": {
                    "node_id": {"type": "keyword"},
                    "label": {"type": "text"},
                    "type": {"type": "keyword"},
                    "summary": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "summary_embedding": {
                        "type": "dense_vector",
                        "dims": self.embedding_dim,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "properties": {"type": "object"},
                    "created_at": {"type": "date"},
                    "graph_id": {"type": "keyword"}
                }
            }
        }

        # Edge index mapping with embedding support
        edges_mapping = {
            "mappings": {
                "properties": {
                    "edge_id": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "target": {"type": "keyword"},
                    "label": {"type": "text"},
                    "type": {"type": "keyword"},
                    "summary": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "summary_embedding": {
                        "type": "dense_vector",
                        "dims": self.embedding_dim,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "properties": {"type": "object"},
                    "created_at": {"type": "date"},
                    "graph_id": {"type": "keyword"}
                }
            }
        }

        try:
            if not self.es.indices.exists(index=self.nodes_index):
                self.es.indices.create(index=self.nodes_index, body=nodes_mapping)
                logger.info(f"Created index: {self.nodes_index}")

            if not self.es.indices.exists(index=self.edges_index):
                self.es.indices.create(index=self.edges_index, body=edges_mapping)
                logger.info(f"Created index: {self.edges_index}")

        except Exception as e:
            logger.error(f"Error creating indices: {e}")
            raise

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for given text using the sentence transformer model."""
        if not text or text.strip() == "":
            return [0.0] * self.embedding_dim

        try:
            embedding = self.embedding_model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding for text: {e}")
            return [0.0] * self.embedding_dim

    def add_graph_to_elasticsearch(self, graph_json: Dict[str, Any], graph_id: Optional[str] = None) -> bool:
        """
        Add a complete graph (nodes and edges) to Elasticsearch with embeddings.

        Args:
            graph_json: Dictionary containing 'nodes' and 'edges' lists
            graph_id: Optional identifier for the graph

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract nodes and edges from graph JSON
            nodes = graph_json.get('nodes', [])
            edges = graph_json.get('edges', [])

            if not graph_id:
                graph_str = json.dumps(graph_json, sort_keys=True)
                graph_id = hashlib.md5(graph_str.encode()).hexdigest()[:16]

            # Add nodes and edges
            nodes_success = self.add_nodes(nodes, graph_id)
            edges_success = self.add_edges(edges, graph_id)

            return nodes_success and edges_success

        except Exception as e:
            logger.error(f"Error adding graph to Elasticsearch: {e}")
            return False

    def add_nodes(self, nodes: List[Dict[str, Any]], graph_id: str) -> bool:
        """
        Add nodes to Elasticsearch with embeddings for summary field.

        Args:
            nodes: List of node dictionaries
            graph_id: Identifier for the graph these nodes belong to

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            actions = []

            for node in nodes:
                summary = node.get('summary', '')
                summary_embedding = self._generate_embedding(summary) if summary else None

                node_doc = {
                    "node_id": node.get('id', ''),
                    "label": node.get('label', ''),
                    "type": node.get('type', ''),
                    "summary": summary,
                    "properties": node.get('properties', {}),
                    "graph_id": graph_id,
                    "created_at": "now"
                }

                if summary_embedding:
                    node_doc["summary_embedding"] = summary_embedding

                action = {
                    "_index": self.nodes_index,
                    "_id": f"{graph_id}_{node.get('id', '')}",
                    "_source": node_doc
                }
                actions.append(action)

            if actions:
                success, failed = bulk(self.es, actions)
                logger.info(f"Added {success} nodes to Elasticsearch")

                if failed:
                    logger.warning(f"Failed to add {len(failed)} nodes")

                return len(failed) == 0

            return True

        except Exception as e:
            logger.error(f"Error adding nodes: {e}")
            return False

    def add_edges(self, edges: List[Dict[str, Any]], graph_id: str) -> bool:
        """
        Add edges to Elasticsearch with embeddings for summary field.

        Args:
            edges: List of edge dictionaries
            graph_id: Identifier for the graph these edges belong to

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            actions = []

            for edge in edges:
                summary = edge.get('summary', '')
                summary_embedding = self._generate_embedding(summary) if summary else None

                edge_doc = {
                    "edge_id": edge.get('id', ''),
                    "source": edge.get('source', ''),
                    "target": edge.get('target', ''),
                    "label": edge.get('label', ''),
                    "type": edge.get('type', ''),
                    "summary": summary,
                    "properties": edge.get('properties', {}),
                    "graph_id": graph_id,
                    "created_at": "now"
                }

                if summary_embedding:
                    edge_doc["summary_embedding"] = summary_embedding

                action = {
                    "_index": self.edges_index,
                    "_id": f"{graph_id}_{edge.get('id', '')}",
                    "_source": edge_doc
                }
                actions.append(action)

            if actions:
                success, failed = bulk(self.es, actions)
                logger.info(f"Added {success} edges to Elasticsearch")

                if failed:
                    logger.warning(f"Failed to add {len(failed)} edges")

                return len(failed) == 0

            return True

        except Exception as e:
            logger.error(f"Error adding edges: {e}")
            return False
