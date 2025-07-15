# Trusted Code: Python to WhyML Converter

A framework that automatically translates Python functions into Why3 specifications for formal verification. The system uses LangGraph for workflow orchestration and Claude for code translation, with iterative error correction and a capability gap analysis.

The system follows a multi-stage pipeline:

1. **Type Enhancement**: Adds type hints to Python functions
2. **WhyML Translation**: Converts typed Python to WhyML specifications
3. **Formal Verification**: Executes code using Why3 prover
4. **Error Correction**: Iteratively fixes errors using LLM

## Prerequisites

### System Dependencies

**Python 3.13**

**Why3 Theorem Prover**, along with Alt-Ergo SMT solver

**Ubuntu/Debian**
```bash
sudo apt-get install why3
```

**macOS (with Homebrew)**
```bash
brew install why3
```

Or build from source: https://why3.lri.fr/

**Alt-Ergo Prover**: Recommended prover backend
```bash
opam install alt-ergo
```

### API Requirements

**Anthropic API Key**: For Claude integration (Other LLM's can be used including LocalLLama).

Create a `.env` file and paste:
```
ANTHROPIC_API_KEY = "your_api_key_here"
```

## Installation

This project uses UV for fast Python package management

1. Clone the repo
2. Navigate to the directory using `cd TrustedCode`
3. Use curl to install uv 
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
4. Install dependencies using the `uv sync` command
5. If `uv sync` does not work, install the following dependencies
6. ```
   dependencies = [
       "graphviz>=0.21",
       "langchain>=0.3.25", 
       "langchain-anthropic>=0.3.15",
       "langchain-core>=0.3.65",
       "langgraph>=0.4.8",
       "langsmith>=0.3.45",
       "pandas>=2.3.0",
       "python-dotenv>=1.1.0"]
   ```

## Usage

Run directly from the command line interface as follows:
```bash
uv run main.py path/to/python.py
```

## Output

**Results Table**: Comprehensive analysis saved to `whyml_conversion_results.csv`

**Graph Visualization**: Workflow diagram saved as `graph_visualization.png`
