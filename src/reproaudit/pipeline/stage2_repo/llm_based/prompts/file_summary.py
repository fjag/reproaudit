SYSTEM = (
    "You are a code analysis assistant specializing in ML and computational biology research code. "
    "Be concise and precise."
)

def build(file_path: str, code: str) -> str:
    return f"""\
Summarize the following Python file from a research code repository.

File: {file_path}

Provide:
1. role: One of: data_loading, preprocessing, model_definition, training, evaluation, inference, visualisation, utility, configuration, pipeline_orchestration, other
2. summary: 2-3 sentences describing what this file does in the ML pipeline context.
3. key_symbols: The most important function and class names (up to 8).

--- CODE ---
{code[:6000]}
--- END CODE ---
"""
