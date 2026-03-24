from langchain.tools import StructuredTool

from agents.agent_registry.data_analysis_agent.tools_impl.repl_funcs import REPLFuncs


def create_query_repl_func_descriptions():

    func_list = sum(REPLFuncs.values(), [])

    func_dict = {func.name: func.description for func in func_list}

    def query_repl_func_descriptions(func_name: str) -> str:
        func_description = func_dict.get(func_name, "")
        if func_description:
            return func_description
        else:
            return (
                "Error: provided function name does not match existing function. Valid functions names: "
                + ", ".join(list(func_dict.keys()))
            )

    return query_repl_func_descriptions


QueryReplFuncDescriptionsToolDescription = " ".join(
    """Retrieves the corresponding
function description (overview, arguments, input / return format) from a function name.
Input an empty string to get a list of all functions avaliable for use in the REPL.""".splitlines()
)

query_repl_func_descriptions_tool = StructuredTool.from_function(
    func=create_query_repl_func_descriptions(),
    name="query_repl_func_descriptions",
    description=QueryReplFuncDescriptionsToolDescription,
)
