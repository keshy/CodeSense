import streamlit as st
import os
import shutil
from pathlib import Path
import git
from urllib.parse import urlparse
import logging

try:
    from code2flow import engine as cfe
except ImportError:
    st.error("code2flow module not found. Please ensure it's installed or available in the current directory.")
    st.stop()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_directories():
    """Create necessary directories if they don't exist."""
    Path("slurp/resources/code").mkdir(parents=True, exist_ok=True)
    Path("slurp/resources/cf").mkdir(parents=True, exist_ok=True)


def extract_repo_name(github_url):
    """Extract repository name from GitHub URL."""
    try:
        parsed_url = urlparse(github_url)
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) >= 2:
            return f"{path_parts[0]}_{path_parts[1]}"
        return "unknown_repo"
    except Exception as e:
        logger.error(f"Error extracting repo name: {e}")
        return "unknown_repo"


def clone_repository(github_url, destination_path):
    """Clone GitHub repository to destination path."""
    try:
        # Remove existing directory if it exists
        if os.path.exists(destination_path):
            shutil.rmtree(destination_path)

        # Clone the repository
        git.Repo.clone_from(github_url, destination_path)
        return True, None
    except Exception as e:
        return False, str(e)


def get_supported_languages():
    """Get list of supported languages for code2flow."""
    return [
        'python', 'py',
        'javascript', 'js',
        'typescript', 'ts',
        'java',
        'c', 'cpp', 'c++',
        'php',
        'ruby', 'rb',
        'go',
        'swift',
        'kotlin'
    ]


def generate_callflow_graph(source_path, output_path, language=None, **kwargs):
    """Generate call flow graph using code2flow."""
    try:
        # Set up parameters
        lang_params = cfe.LanguageParams()

        # Configure output file
        output_file = os.path.join(output_path, "call_flow.json")

        # Call code2flow
        cfe.code2flow(
            raw_source_paths=[source_path],
            output_file=output_file,
            language=language,
            hide_legend=kwargs.get('hide_legend', False),
            exclude_namespaces=kwargs.get('exclude_namespaces', None),
            exclude_functions=kwargs.get('exclude_functions', None),
            include_only_namespaces=kwargs.get('include_only_namespaces', None),
            include_only_functions=kwargs.get('include_only_functions', None),
            no_grouping=kwargs.get('no_grouping', False),
            no_trimming=kwargs.get('no_trimming', False),
            skip_parse_errors=kwargs.get('skip_parse_errors', True),
            lang_params=lang_params,
            level=logging.INFO,
            exclude_lib_files=kwargs.get('exclude_lib_files', True)
        )

        return True, output_file
    except Exception as e:
        return False, str(e)


def main():
    st.set_page_config(
        page_title="GitHub Code Flow Analyzer",
        page_icon="🔄",
        layout="wide"
    )

    st.title("🔄 GitHub Code Flow Analyzer")
    st.markdown("Generate call flow graphs from public GitHub repositories using code2flow")

    # Create necessary directories
    create_directories()

    # Sidebar for configuration
    st.sidebar.header("Configuration")

    # GitHub URL input
    github_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/username/repository",
        help="Enter the URL of a public GitHub repository"
    )

    # Language selection
    languages = get_supported_languages()
    selected_language = st.sidebar.selectbox(
        "Programming Language (Auto-detect if not specified)",
        options=["auto-detect"] + languages,
        index=0
    )

    # Advanced options
    st.sidebar.subheader("Advanced Options")

    hide_legend = st.sidebar.checkbox("Hide Legend", value=False)
    no_grouping = st.sidebar.checkbox("No Grouping", value=False)
    no_trimming = st.sidebar.checkbox("No Trimming", value=False)
    skip_parse_errors = st.sidebar.checkbox("Skip Parse Errors", value=True)
    exclude_lib_files = st.sidebar.checkbox("Exclude Library Files", value=True)

    # Exclusion/Inclusion filters
    with st.sidebar.expander("Filters (Optional)"):
        exclude_namespaces = st.text_area(
            "Exclude Namespaces (one per line)",
            help="List of namespaces to exclude from the graph"
        )
        exclude_functions = st.text_area(
            "Exclude Functions (one per line)",
            help="List of functions to exclude from the graph"
        )
        include_only_namespaces = st.text_area(
            "Include Only Namespaces (one per line)",
            help="List of namespaces to include (excludes all others)"
        )
        include_only_functions = st.text_area(
            "Include Only Functions (one per line)",
            help="List of functions to include (excludes all others)"
        )

    # Process filters
    def process_filter_text(text):
        if text:
            return [line.strip() for line in text.split('\n') if line.strip()]
        return None

    exclude_namespaces_list = process_filter_text(exclude_namespaces)
    exclude_functions_list = process_filter_text(exclude_functions)
    include_only_namespaces_list = process_filter_text(include_only_namespaces)
    include_only_functions_list = process_filter_text(include_only_functions)

    # Main content area
    col1, col2 = st.columns([3, 1])

    with col2:
        generate_button = st.button("🚀 Generate Flow Graph", type="primary")

    if generate_button and github_url:
        # Validate GitHub URL
        if not github_url.startswith(('https://github.com/', 'http://github.com/')):
            st.error("Please enter a valid GitHub URL")
            st.stop()

        # Extract repository name
        repo_name = extract_repo_name(github_url)
        source_path = f"resources/code/{repo_name}"
        output_path = f"resources/cf/{repo_name}"

        # Create output directory
        Path(output_path).mkdir(parents=True, exist_ok=True)

        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # Step 1: Clone repository
            status_text.text("🔄 Cloning repository...")
            progress_bar.progress(25)

            success, error = clone_repository(github_url, source_path)
            if not success:
                st.error(f"Failed to clone repository: {error}")
                st.stop()

            st.success(f"✅ Repository cloned to: {source_path}")

            # Step 2: Generate call flow graph
            status_text.text("🔄 Generating call flow graph...")
            progress_bar.progress(50)

            # Prepare parameters
            lang = None if selected_language == "auto-detect" else selected_language

            kwargs = {
                'hide_legend': hide_legend,
                'exclude_namespaces': exclude_namespaces_list,
                'exclude_functions': exclude_functions_list,
                'include_only_namespaces': include_only_namespaces_list,
                'include_only_functions': include_only_functions_list,
                'no_grouping': no_grouping,
                'no_trimming': no_trimming,
                'skip_parse_errors': skip_parse_errors,
                'exclude_lib_files': exclude_lib_files
            }

            success, result = generate_callflow_graph(source_path, output_path, lang, **kwargs)

            progress_bar.progress(75)

            if not success:
                st.error(f"Failed to generate call flow graph: {result}")
                st.stop()

            # Step 3: Display results
            status_text.text("🔄 Processing results...")
            progress_bar.progress(100)

            st.success(f"✅ Call flow graph generated successfully!")

            # Display the generated graph
            if os.path.exists(result):
                st.subheader("📊 Generated Call Flow Graph")
                with open(result, 'r') as f:
                    st.json(f.read(), expanded=False)
            # Display repository information
            st.subheader("📁 Repository Information")

            # Count files by extension
            file_counts = {}
            total_files = 0

            for root, dirs, files in os.walk(source_path):
                # Skip hidden directories and common non-source directories
                dirs[:] = [d for d in dirs if
                           not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', 'env']]

                for file in files:
                    if not file.startswith('.'):
                        ext = Path(file).suffix.lower()
                        if ext:
                            file_counts[ext] = file_counts.get(ext, 0) + 1
                            total_files += 1

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Files", total_files)

            with col2:
                st.metric("File Types", len(file_counts))

            with col3:
                repo_size = sum(
                    os.path.getsize(os.path.join(root, file))
                    for root, dirs, files in os.walk(source_path)
                    for file in files
                ) / (1024 * 1024)  # Convert to MB
                st.metric("Repository Size", f"{repo_size:.2f} MB")

            # Display file type breakdown
            if file_counts:
                st.subheader("📋 File Type Breakdown")

                # Sort by count
                sorted_counts = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)

                for ext, count in sorted_counts[:10]:  # Show top 10
                    st.write(f"**{ext}**: {count} files")

            # Display generated files
            st.subheader("📄 Generated Files")

            output_files = []
            if os.path.exists(output_path):
                for file in os.listdir(output_path):
                    file_path = os.path.join(output_path, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        output_files.append({
                            'name': file,
                            'size': f"{file_size / 1024:.2f} KB",
                            'path': file_path
                        })

            if output_files:
                for file_info in output_files:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"📄 {file_info['name']}")
                    with col2:
                        st.write(file_info['size'])
                    with col3:
                        if file_info['name'].endswith('.json'):
                            with open(file_info['path'], 'r') as f:
                                st.download_button(
                                    "Download",
                                    data=f.read(),
                                    file_name=file_info['name'],
                                    mime="image/svg+xml",
                                    key=f"download_{file_info['name']}"
                                )

            status_text.text("✅ Complete!")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            logger.error(f"Error in main process: {e}", exc_info=True)

    elif generate_button and not github_url:
        st.warning("Please enter a GitHub repository URL")


if __name__ == "__main__":
    main()
