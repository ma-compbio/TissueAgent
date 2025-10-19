from api_keys import APIKeys
from agents.agent_utils import file_retriever_tool
from agents.agent_registry.data_analysis_agent.rag_impl.code_rag_tool import create_code_rag_tool
from agents.agent_registry.data_analysis_agent.tools_impl.python_repl_tool import create_python_repl_tool
from agents.agent_registry.data_analysis_agent.tools_impl.query_repl_func_descriptions_tool import query_repl_func_descriptions_tool


def create_data_analysis_tools(api_keys: APIKeys):
    python_repl_exec_tool, python_repl_log_tool = create_python_repl_tool()
    code_rag_tool = create_code_rag_tool(api_keys)

    return [python_repl_exec_tool,
            python_repl_log_tool,
            file_retriever_tool,
            code_rag_tool]

DataAnalysisTools: List[StructuredTool] = [
    python_repl_exec_tool

    
]
