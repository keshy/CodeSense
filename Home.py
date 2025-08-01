import streamlit as st
import os

st.set_page_config(
    page_title="GitHub Code Flow Analyzer",
    page_icon="🔄",
    layout="wide"
)

st.title("🔄 GitHub Code Flow Analyzer")
st.markdown("Generate call flow graphs from public GitHub repositories using code2flow")

# Display information about the application
with st.expander("ℹ️ About this Application"):
    st.markdown("""
                This application uses the **code2flow** library to generate call flow graphs from GitHub repositories.

                **Features:**
                - Clone public GitHub repositories
                - Generate interactive call flow diagrams
                - Support for multiple programming languages
                - Customizable filtering options
                - Download generated graphs

                **Supported Languages:**
                Python, JavaScript, TypeScript, Java, C/C++, PHP, Ruby, Go, Swift, Kotlin

                **How it works:**
                1. Enter a public GitHub repository URL
                2. Configure analysis options (optional)
                3. Click "Generate Flow Graph"
                4. View and download the generated call flow diagram

                **Note:** Large repositories may take several minutes to process.
                """)

    # Display current directories status
with st.expander("📂 Directory Status"):
    code_dir = "resources/code"
    cf_dir = "resources/cf"

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Code Directory:**")
        if os.path.exists(code_dir):
            repos = [d for d in os.listdir(code_dir) if os.path.isdir(os.path.join(code_dir, d))]
            if repos:
                for repo in repos:
                    st.write(f"📁 {repo}")
            else:
                st.write("No repositories cloned yet")
        else:
            st.write("Directory not created yet")

    with col2:
        st.write("**Call Flow Directory:**")
        if os.path.exists(cf_dir):
            graphs = [d for d in os.listdir(cf_dir) if os.path.isdir(os.path.join(cf_dir, d))]
            if graphs:
                for graph in graphs:
                    st.write(f"📊 {graph}")
            else:
                st.write("No graphs generated yet")
        else:
            st.write("Directory not created yet")
