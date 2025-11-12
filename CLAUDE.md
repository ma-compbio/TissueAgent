# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TissueAgent is an autonomous AI agent system for spatial transcriptomics research, built using LangGraph and Streamlit. The system uses a multi-agent architecture where specialized agents collaborate to execute complex bioinformatics tasks.

## Setup and Development Commands

### Initial Setup
```bash
# Install Python 3.12 and uv package manager
uv sync  # Install all dependencies from pyproject.toml
```

### Running the Application
```bash
source .venv/bin/activate
PYTHONPATH=$(pwd)/src python -m streamlit run src/app.py
```

### Development Tools
```bash
# Add new dependencies
uv add [package]
```

Note: There is no test suite currently in this repository.

## Architecture Overview

### Multi-Agent System Flow

The system implements a hierarchical agent workflow:

1. **Planner Agent** - Analyzes user queries and creates execution plans
   - Routes to: Direct response, Clarification request, or Plan creation
   - Decides between ROUTE: DIRECT, ROUTE: CLARIFY, or ROUTE: PLAN

2. **Recruiter Agent** - Assigns specialized agents to plan steps

3. **Manager Agent** - Coordinates execution of the plan
   - Invokes specialized agents sequentially
   - Validates artifacts and manages retries
   - Ensures all paths are relative to DATA_DIR

4. **Evaluator Agent** - Validates results
   - Routes to: Replanning or Reporting

5. **Reporter Agent** - Generates final outputs and Jupyter notebooks

### Specialized Agents (Agent Registry)

Located in `src/agents/agent_registry/`:

- **Coding Agent** - Custom agent using CodeAct pattern for executing Python code with spatial transcriptomics libraries (scanpy, squidpy, liana)
  - Uses `<execute>` blocks for code execution
  - Uses `<scratchpad>` blocks for reasoning
  - Maintains a persistent Python REPL session
  - Has access to documentation and tutorial RAG tools

- **Searcher Agent** - Literature search via PubMed and Google Scholar

- **Single Cell Agent** - CellxGene census queries and cell2location deconvolution

- **Gene Agent** - Gene-related analysis tasks

### Graph Structure

The main graph is defined in `src/graph/graph.py`:
- Uses LangGraph's StateGraph with MessagesState
- Each main agent has an agent node and a tool node
- Agents are connected with conditional edges based on routing logic
- Subagents are compiled as separate graphs and invoked as tools by Manager Agent

### Agent Types

Two agent patterns are used:

1. **ReActAgent** - Standard LangGraph agent with tools
   - Defined with: id, name, description, prompt, tools, model_ctor

2. **CustomAgent** - Custom implementation (e.g., Coding Agent)
   - Defined with: id, name, description, ctor (constructor function)

All agent definitions are in `src/agents/agent_defns.py`.

### Data Flow and File Management

- **DATA_DIR**: Root workspace directory (`/data`)
- **DATASET_DIR**: Uploaded datasets (`/data/dataset`)
- **UPLOADS_DIR**: Uploaded images (`/data/uploads`)
- **PDF_UPLOADS_DIR**: Uploaded PDFs (`/data/pdfs`)
- **NOTEBOOK_DIR**: Generated Jupyter notebooks (`/data/notebook`)
- **SESSIONS_DIR**: Saved chat sessions (`/sessions`)

All artifact paths MUST be relative to DATA_DIR.

### State Management

- Main application state stored in Streamlit's `st.session_state`
- Agent state uses LangGraph's MessagesState
- Coding Agent maintains a persistent PythonREPL between executions
- Subagent states are queued and displayed in the UI

## Key Implementation Details

### Coding Agent Pattern

The Coding Agent uses a unique CodeAct pattern:
- Operates on CodeActState (extends MessagesState)
- Agent node generates code or responses
- Exec node runs code in persistent REPL
- Uses `extract_block()` to parse `<execute>` and `<scratchpad>` blocks
- Has access to documentation_index_tool and tutorial_index_tool

### Model Configuration

Default model: `gpt-5` (defined in `agent_defns.py` as DefaultModelCtor)
- All agents use GPT-5 by default
- Model can be bound with retry logic for rate limiting

### Tool Invocation

- Tools are bound to agents using LangGraph's tool binding
- Subagents are invoked as tools via `create_agent_invocation_tool()`
- Manager Agent receives all subagent tools dynamically

### Recursion and Error Handling

- Recursion limit: 50 (RECURSION_LIMIT in config.py)
- GraphRecursionError caught in app.py
- BadRequestError from Anthropic/OpenAI caught and displayed

## Known Issues

- Coding agent often requires multiple iterations to format responses correctly
- Evaluator agent doesn't support multi-modal input or inspect artifact contents
- Gene agent and searcher agent cannot generate expected files reliably
- PDF understanding not tested
- Prompt format differs between agents
- All agents default to GPT-5; weaker models could be used for simpler agents

## File Organization

```
src/
├── agents/
│   ├── agent_defns.py          # Central agent registry
│   ├── agent_utils.py          # Shared utilities
│   ├── planner_agent/          # Planning and routing
│   ├── recruiter_agent/        # Agent assignment
│   ├── manager_agent/          # Execution coordination
│   ├── evaluator_agent/        # Result validation
│   ├── reporter_agent/         # Output generation
│   └── agent_registry/         # Specialized agents
│       ├── coding_agent/       # Python execution + RAG
│       ├── searcher_agent/     # Literature search
│       ├── single_cell_agent/  # CellxGene integration
│       └── gene_agent/         # Gene analysis
├── graph/
│   ├── graph.py               # Main graph construction
│   └── graph_utils.py         # Graph utilities
├── app.py                     # Streamlit UI
├── app_utils.py              # UI utilities
└── config.py                 # Global configuration
```

## Common Development Patterns

### Adding a New Agent

1. Create directory in `src/agents/agent_registry/[agent_name]/`
2. Define prompt.py with AgentPrompt and AgentDescription
3. Define tools.py with tool list
4. Add to `agent_defns.py` as ReActAgent or CustomAgent
5. Import in `agent_defns.py` and add to AgentDefns list

### Modifying Agent Behavior

- Agent prompts are in each agent's `prompt.py`
- Tools are in each agent's `tools.py` with implementations in `tools_impl/`
- Router logic is in `graph.py` (e.g., planner_router, evaluator_router)

### Working with Coding Agent

- Coding Agent uses special block syntax in prompts
- Code execution happens in a stateful REPL
- Documentation RAG uses embeddings from scanpy/squidpy/liana docs
- Tutorial index returns full tutorial file contents
