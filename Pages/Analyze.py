import json
from pathlib import Path
from typing import Dict, Any

import streamlit as st


def load_available_callflows():
    """Load all available call flow graphs from resources/cf directory."""
    cf_dir = Path("resources/cf/")
    callflows = {}

    if cf_dir.exists():
        for item in cf_dir.iterdir():
            if item.is_dir():
                print(item)
                json_file = item / "call_flow.json"
                if json_file.exists():
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            graph_data = json.load(f)
                        callflows[item.name] = {
                            'path': str(json_file),
                            'data': graph_data,
                            'metadata': graph_data.get('metadata', {}),
                            'node_count': len(graph_data.get('nodes', [])),
                            'edge_count': len(graph_data.get('edges', []))
                        }
                    except Exception as e:
                        st.error(f"Error loading {json_file}: {e}")

    return callflows


def process_natural_language_query(query: str, graph_data: Dict[str, Any], selected_callflow: str) -> str:
    """
    Process natural language query against the graph data.

    This is a stub function - implement your NLP/RAG logic here.

    Args:
        query: The natural language query from the user
        graph_data: The complete graph data structure
        selected_callflow: Name of the selected callflow

    Returns:
        str: Markdown formatted response
    """
    # TODO: Implement actual NLP/RAG processing
    # This is where you would:
    # 1. Process the query using your NLP model
    # 2. Search through graph embeddings
    # 3. Retrieve relevant nodes/edges
    # 4. Generate a natural language response

    # For now, return a placeholder response
    return f"""
## Query Analysis Results

**Your Query:** "{query}"

**Selected Callflow:** `{selected_callflow}`

### Analysis Summary
This is a placeholder response. The actual implementation will:

1. **Parse your natural language query** using NLP techniques
2. **Search through graph embeddings** to find relevant code sections
3. **Analyze call flows and relationships** based on your question
4. **Generate contextual responses** about the codebase

### Graph Context
- **Total Nodes:** {len(graph_data.get('nodes', []))}
- **Total Edges:** {len(graph_data.get('edges', []))}
- **Graph Type:** Call Flow Analysis

### Suggested Queries
Try asking questions like:
- "What functions call the main method?"
- "Show me the data flow for user authentication"
- "Which modules have the highest complexity?"
- "What are the entry points of this application?"

---
*🔧 This feature is currently in development. Your query has been logged for processing.*
    """


def display_query_history():
    """Display and manage query history."""
    if 'query_history' not in st.session_state:
        st.session_state.query_history = []

    if st.session_state.query_history:
        st.subheader("📝 Query History")

        for i, (query, timestamp) in enumerate(reversed(st.session_state.query_history[-5:])):
            with st.expander(f"Query {len(st.session_state.query_history) - i}: {query[:50]}..."):
                st.write(f"**Query:** {query}")
                st.write(f"**Time:** {timestamp}")
                if st.button(f"Rerun Query", key=f"rerun_{i}"):
                    st.session_state.current_query = query


def main():
    st.set_page_config(
        page_title="Code Analysis - Natural Language Queries",
        page_icon="🔍",
        layout="wide"
    )

    st.title("🔍 Code Analysis - Natural Language Queries")
    st.markdown(
        "Ask questions about your code using natural language and get intelligent responses based on call flow analysis.")

    # Load available call flows
    callflows = load_available_callflows()

    if not callflows:
        st.warning("No call flow graphs found in `resources/cf/` directory.")
        st.info("Please generate some call flow graphs first using the onboarding page.")
        st.stop()

    # Sidebar for callflow selection
    st.sidebar.header("📊 Select Repository to Analyze")

    selected_callflow = st.sidebar.selectbox(
        "Choose a call flow to analyze:",
        options=list(callflows.keys()),
        format_func=lambda x: f"{x} ({callflows[x]['node_count']} nodes, {callflows[x]['edge_count']} edges)"
    )

    if selected_callflow:
        graph_info = callflows[selected_callflow]
        graph_data = graph_info['data']

        # Main content area
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader(f"📊 Analyzing: {selected_callflow}")

        # Natural Language Query Interface
        st.markdown("---")
        st.subheader("💬 Ask Questions About Your Code")

        # Initialize session state for current query
        if 'current_query' not in st.session_state:
            st.session_state.current_query = ""

        # Query input
        col1, col2 = st.columns([4, 1])

        with col1:
            query = st.text_input(
                "Enter your question:",
                value=st.session_state.current_query,
                placeholder="e.g., 'What functions are called by the main method?' or 'Show me the authentication flow'",
                help="Ask questions about function calls, data flow, dependencies, or code structure"
            )

        with col2:
            st.markdown("<br>", unsafe_allow_html=True)  # Add some spacing
            search_button = st.button("🔍 Search", type="primary")

        # Example queries
        st.markdown("**💡 Example queries:**")
        example_queries = [
            "What functions call the main method?",
            "Show me all entry points in this code",
            "Which functions have the most dependencies?",
            "What is the call hierarchy for authentication?",
            "Find all functions that handle user input",
            "Show me the data flow for error handling"
        ]

        cols = st.columns(3)
        for i, example in enumerate(example_queries):
            with cols[i % 3]:
                if st.button(f"📝 {example}", key=f"example_{i}"):
                    st.session_state.current_query = example
                    query = example
                    search_button = True

        # Process query
        if (search_button and query) or st.session_state.current_query:
            if query or st.session_state.current_query:
                current_query = query or st.session_state.current_query

                # Add to query history
                if 'query_history' not in st.session_state:
                    st.session_state.query_history = []

                import datetime
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Only add if it's a new query
                if not st.session_state.query_history or st.session_state.query_history[-1][0] != current_query:
                    st.session_state.query_history.append((current_query, timestamp))

                # Show loading spinner
                with st.spinner("🔍 Analyzing your query..."):
                    # Process the query
                    response = process_natural_language_query(current_query, graph_data, selected_callflow)

                # Display results
                st.markdown("---")
                st.subheader("📋 Analysis Results")

                # Display the response in markdown
                st.markdown(response)

                # Additional context section
                with st.expander("🔍 Query Context & Graph Details"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Query Information:**")
                        st.write(f"- **Query:** {current_query}")
                        st.write(f"- **Callflow:** {selected_callflow}")
                        st.write(f"- **Timestamp:** {timestamp}")
                        st.write(f"- **Graph Nodes:** {len(graph_data.get('nodes', []))}")
                        st.write(f"- **Graph Edges:** {len(graph_data.get('edges', []))}")

                    with col2:
                        st.markdown("**Available Node Types:**")
                        node_types = {}
                        for node in graph_data.get('nodes', []):
                            node_type = node.get('type', 'unknown')
                            node_types[node_type] = node_types.get(node_type, 0) + 1

                        for node_type, count in node_types.items():
                            st.write(f"- **{node_type}:** {count}")

                # Clear current query
                st.session_state.current_query = ""

        # Display query history
        if st.session_state.get('query_history'):
            st.markdown("---")
            display_query_history()

        # Graph Details Section
        st.markdown("---")


if __name__ == "__main__":
    main()
