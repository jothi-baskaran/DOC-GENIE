import streamlit as st
import ast
import google.generativeai as genai
import textwrap
from typing import List, Dict, Any

# ==========================================
# CORE ENGINE: AST ANALYSIS & TRANSFORMATION
# ==========================================

class DocGenieCore:
    """Handles the parsing and rewriting of Python files using AST."""
    
    @staticmethod
    def get_function_source(node: ast.AST, full_source: str) -> str:
        """Extracts the raw source code of a specific node."""
        return textwrap.dedent("\n".join(full_source.splitlines()[node.lineno-1 : node.end_lineno]))

    class DocstringInjector(ast.NodeTransformer):
        """Walks the AST and injects AI-generated docstrings into functions."""
        def __init__(self, doc_map: Dict[str, str]):
            self.doc_map = doc_map

        def visit_FunctionDef(self, node: ast.FunctionDef):
            # Only inject if we have a generated docstring for this function
            if node.name in self.doc_map:
                new_doc = self.doc_map[node.name]
                doc_node = ast.Expr(value=ast.Constant(value=new_doc))
                
                # Check if function already has a docstring
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, ast.Constant) and 
                    isinstance(node.body[0].value.value, str)):
                    # Replace existing
                    node.body[0] = doc_node
                else:
                    # Insert at the start
                    node.body.insert(0, doc_node)
            return node

# ==========================================
# AI ENGINE: GEMINI INTEGRATION
# ==========================================

class AIService:
    """Handles communication with the LLM."""
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def generate_doc(self, code_snippet: str, style: str) -> str:
        prompt = f"""
        Act as a senior Python developer. Generate a professional {style}-style docstring 
        for the following code. Include:
        1. Brief description
        2. Args (with types)
        3. Returns (with types)
        4. Raises (if any)

        Return ONLY the docstring text, starting and ending with triple quotes.
        CODE:
        {code_snippet}
        """
        try:
            response = self.model.generate_content(prompt)
            # Clean formatting to ensure only the docstring is returned
            clean_doc = response.text.strip()
            if not clean_doc.startswith('"""'): clean_doc = f'"""\n{clean_doc}\n"""'
            return clean_doc
        except Exception as e:
            return f'"""Error generating docstring: {str(e)}"""'

# ==========================================
# UI LAYER: STREAMLIT INTERFACE
# ==========================================

def main():
    st.set_page_config(page_title="DOC GENIE", page_icon="🧞", layout="wide")
    
    st.title("🧞 DOC GENIE: Professional AST Doc Generator")
    st.markdown("---")

    # Sidebar Settings
    st.sidebar.header("Genie Settings")
    api_key = st.sidebar.text_input("Gemini API Key", type="password")
    doc_style = st.sidebar.selectbox("Docstring Style", ["Google", "NumPy", "Sphinx"])
    
    # File Upload "Box"
    uploaded_file = st.file_uploader("📤 Upload a Python (.py) File", type=["py"])

    if uploaded_file and api_key:
        source_code = uploaded_file.read().decode("utf-8")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Original Code")
            st.code(source_code, language="python")

        if st.button("✨ Run Doc Genie"):
            with st.spinner("Analyzing AST and summoning AI..."):
                try:
                    # 1. Parse AST to find functions
                    tree = ast.parse(source_code)
                    functions_to_process = []
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            functions_to_process.append(node)

                    # 2. Generate Docstrings via AI
                    ai = AIService(api_key)
                    doc_map = {}
                    
                    progress_bar = st.progress(0)
                    for i, func in enumerate(functions_to_process):
                        snippet = DocGenieCore.get_function_source(func, source_code)
                        docstring = ai.generate_doc(snippet, doc_style)
                        doc_map[func.name] = docstring
                        progress_bar.progress((i + 1) / len(functions_to_process))

                    # 3. Transform AST and Unparse
                    injector = DocGenieCore.DocstringInjector(doc_map)
                    new_tree = injector.visit(tree)
                    ast.fix_missing_locations(new_tree)
                    
                    final_code = ast.unparse(new_tree)

                    # 4. Show Result
                    with col2:
                        st.subheader("Documented Code")
                        st.code(final_code, language="python")
                        
                        st.download_button(
                            label="💾 Download Documented File",
                            data=final_code,
                            file_name=f"documented_{uploaded_file.name}",
                            mime="text/x-python"
                        )
                    st.success(f"Successfully documented {len(functions_to_process)} functions!")

                except Exception as e:
                    st.error(f"Genie encountered an error: {e}")
                    
    elif not api_key:
        st.info("Please enter your Gemini API Key in the sidebar to start.")

if __name__ == "__main__":
    main()