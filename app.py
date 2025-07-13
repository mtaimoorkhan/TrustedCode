import streamlit as st
from typing import Annotated, TypedDict
import os
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import threading
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_anthropic import ChatAnthropic
from langgraph.graph.message import add_messages
import subprocess
import tempfile
import re
import pandas as pd

load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]
    conversion_timeout: bool = False
    execution_success: bool = False
    retry_count: int = 0
    whyml_code: str = ""
    error_message: str = ""
    original_python: str = ""
    typed_python: str = ""
    whyml_attempts: list = []
    errors: list = []
    capability_gaps: list = []
    full_responses: list = []

# Initialize LLM without caching to ensure fresh state each time
llm = ChatAnthropic(model='claude-3-5-haiku-20241022', temperature=0.1)

TYPING_PROMPT = """Convert the code provided into well-typed python code. add type hints in the function such as int or float as relevant. import relevant libraries as you see fit. You must output raw Python code only. Start directly with 'def' or 'class'. No formatting."""

WHYML_PROMPT = """You are an expert in formal verification using Why3. Convert the following well typed Python function into WhyML. Do NOT use markdown formatting or code blocks. Output only raw WhyML code. start with module and end blocks. import relevant libraries as you see fit."""

ERROR_FIX_PROMPT = """The WhyML code you generated has errors. Fix the code based on the error message. Critically analyse any previous attempts that you made to assist you with the solution.

Original Python Function:
{typed_python}

previous errors and attempts:
{error_history}

Original WhyML code:
{whyml_code}

Error message:
{error_message}


Output ONLY the corrected WhyML code. Do NOT use markdown formatting or code blocks. Output only raw WhyML code. keep the code simple to assist in translation."""

CAPABILITY_GAP_PROMPT = """Classify the following Why3 error into one of these capability gap categories:

Error: {error}

Categories:
1) PTyp - program typing: Python type not translated to equivalent Why3 program type
2) TTyp - theory typing: Python type not translated to equivalent Why3 theory type  
3) STyp - specification typing: Python type not translated to equivalent Why3 specification type
4) PSyn - program syntax: Python syntax not translated to equivalent Why3 program construct
5) TSyn - theory syntax: Python syntax not translated to equivalent Why3 theory construct
6) SSyn - specification syntax: Python syntax not translated to equivalent Why3 specification construct
7) PSem - program semantics: Python semantics not preserved in Why3 program
8) TSem - theory semantics: Python semantics not preserved in Why3 theory
9) SSem - specification semantics: Python semantics not preserved in Why3 specification
10) PKnow - proving knowledge: proving doesn't work automatically with given specification
11) EKnow - environment knowledge: doesn't properly use Why3 environment (API, libraries)
12) DKnow - domain knowledge: doesn't properly use domain specific knowledge

Output the category code (e.g., EKnow) and 20 words max of explination of why you think the capability gap arose:"""

SAMPLE_WHYML_FILE = "sample.mlw"

def clean_whyml_code(code: str) -> str:
    """Remove markdown code blocks and extra formatting from WhyML code"""
    if "```" in code:
        pattern = r'```(?:why|whyml)?\s*\n?(.*?)```'
        match = re.search(pattern, code, re.DOTALL)
        if match:
            code = match.group(1).strip()
        else:
            lines = code.split('\n')
            cleaned_lines = [line for line in lines if not line.strip().startswith('```')]
            code = '\n'.join(cleaned_lines)

    code = code.replace('`', '')

    lines = code.split('\n')
    whyml_lines = []
    for line in lines:
        if line.strip() and not any(phrase in line.lower() for phrase in
                                  ['the code', 'here\'s', 'this is', 'the main', 'changes are',
                                   'looks correct', 'should compile', 'appears to be']):
            whyml_lines.append(line)

    return '\n'.join(whyml_lines).strip()

def classify_capability_gap(error_message: str) -> str:
    """Classify the error into capability gap categories"""
    if not error_message or error_message == "Timeout":
        return "N/A"

    system_msg = SystemMessage(content=CAPABILITY_GAP_PROMPT.format(error=error_message))
    human_msg = HumanMessage(content="Classify this error")

    try:
        response = llm.invoke([system_msg, human_msg])
        classification = response.content.strip()

        valid_categories = ["PTyp", "TTyp", "STyp", "PSyn", "TSyn", "SSyn",
                            "PSem", "TSem", "SSem", "PKnow", "EKnow", "DKnow"]

        for category in valid_categories:
            if classification.startswith(category):
                return classification

        for category in valid_categories:
            if category in classification:
                return classification

        if "module" in error_message.lower() and "not found" in error_message.lower():
            return "EKnow - Module not found in Why3 environment/library"
        elif "type" in error_message.lower():
            return "TTyp - Type translation issue"
        elif "syntax" in error_message.lower():
            return "PSyn - Syntax translation issue"
        else:
            return "Unknown - Could not classify error"
    except Exception:
        return "Unknown - Classification failed"

def chatbot(state: State):
    system_msg = SystemMessage(content=TYPING_PROMPT)
    user_content = state["messages"][-1].content
    human_msg = HumanMessage(content=user_content)

    response = llm.invoke([system_msg, human_msg])

    return {
        "messages": [response],
        "retry_count": 0,
        "original_python": user_content,
        "typed_python": response.content,
        "whyml_attempts": [],
        "errors": [],
        "capability_gaps": []
    }

def whyml_converter(state: State):
    result = {
        "messages": [],
        "conversion_timeout": False,
    }

    def convert():
        try:
            system_msg = SystemMessage(content=WHYML_PROMPT)
            typed_code = state["messages"][-1].content
            human_msg = HumanMessage(content=typed_code)

            response = llm.invoke([system_msg, human_msg])

            cleaned_content = clean_whyml_code(response.content)
            cleaned_response = HumanMessage(content=cleaned_content)
            result["messages"] = [AIMessage(content=cleaned_content)]
        except Exception as e:
            result["messages"] = [HumanMessage(content=f"Conversion error: {str(e)}")]

    thread = threading.Thread(target=convert)
    thread.daemon = True
    thread.start()
    thread.join(timeout=20)

    if thread.is_alive():
        result["conversion_timeout"] = True
        result["messages"] = [HumanMessage(content="TIMEOUT: Using sample file instead")]

    return result

def whyml_executor(state: State):
    if state.get("conversion_timeout", False):
        try:
            with open(SAMPLE_WHYML_FILE, 'r') as f:
                whyml_code = f.read()
        except FileNotFoundError:
            return {
                "messages": [HumanMessage(content=f"Sample file '{SAMPLE_WHYML_FILE}' not found.")],
                "execution_success": False
            }
    else:
        whyml_code = state["messages"][-1].content

    whyml_attempts = state.get("whyml_attempts", [])
    whyml_attempts.append(whyml_code)

    state_update = {
        "whyml_code": whyml_code,
        "whyml_attempts": whyml_attempts,
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.mlw', delete=False) as f:
        f.write(whyml_code)
        temp_filename = f.name

    try:
        result = subprocess.run(['why3', 'prove', '-P', 'alt-ergo', temp_filename],
                                capture_output=True, text=True, timeout=30)

        output = f"WhyML Execution Result:\n"
        if state.get("conversion_timeout", False):
            output += f"(Using sample file: {SAMPLE_WHYML_FILE})\n"
        output += f"Return code: {result.returncode}\n"
        output += f"stdout:\n{result.stdout}\n"
        output += f"stderr:\n{result.stderr}"

        state_update["execution_success"] = (result.returncode == 0)
        state_update["error_message"] = result.stderr if result.returncode != 0 else ""

        if result.returncode != 0:
            errors = state.get("errors", [])
            errors.append(result.stderr)
            state_update["errors"] = errors

            capability_gaps = state.get("capability_gaps", [])
            gap_type = classify_capability_gap(result.stderr)
            capability_gaps.append(gap_type)
            state_update["capability_gaps"] = capability_gaps

        response_msg = HumanMessage(content=output)

    except subprocess.TimeoutExpired:
        response_msg = HumanMessage(content="WhyML execution timed out after 30 seconds")
        state_update["execution_success"] = False
        state_update["error_message"] = "Timeout"
        errors = state.get("errors", [])
        errors.append("Timeout")
        state_update["errors"] = errors
        capability_gaps = state.get("capability_gaps", [])
        capability_gaps.append("N/A")
        state_update["capability_gaps"] = capability_gaps

    except FileNotFoundError:
        response_msg = HumanMessage(content="why3 command not found. Please ensure WhyML is installed and in PATH")
        state_update["execution_success"] = False
        state_update["error_message"] = "why3 not found"
        errors = state.get("errors", [])
        errors.append("why3 not found")
        state_update["errors"] = errors
        capability_gaps = state.get("capability_gaps", [])
        capability_gaps.append("EKnow")
        state_update["capability_gaps"] = capability_gaps

    except Exception as e:
        response_msg = HumanMessage(content=f"Error executing WhyML: {str(e)}")
        state_update["execution_success"] = False
        state_update["error_message"] = str(e)
        errors = state.get("errors", [])
        errors.append(str(e))
        state_update["errors"] = errors
        capability_gaps = state.get("capability_gaps", [])
        capability_gaps.append("Unknown")
        state_update["capability_gaps"] = capability_gaps

    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

    state_update["messages"] = [response_msg]
    return state_update

def error_corrector(state: State):
    ERROR_ANALYSIS_PROMPT = """You are an expert WhyML debugger and formal verification expert with PHD level mathematics knowledge. Your task is to fix a failing WhyML code translation by analyzing the complete history of attempts and errors to identify the root cause. You must not repeat past mistakes. 
    if you keep getting the same error after 2 tries, do not focus on the particular error, instead, focus on the error history and critically analyse the overarching problem you are trying to solve. Be precise, consistent, methodological and write minimal code that satisties the solution. 

    **Original Typed Python Code:**
    ```python
    {typed_python}
    ```
    
    Full History of Failed Attempts:
    You MUST analyze this entire history. Look for recurring errors and flawed assumptions.
    {error_history}

    Your Mandated Task:

    Analysis and Plan (within a <thinking> block):
    Root Cause Analysis: What is the fundamental, recurring error pattern in the history? 
    Action Plan: What is your specific, concrete plan to fix this root cause?
    Corrected WhyML Code:
    Following the <thinking> block, provide ONLY the raw, complete, and corrected WhyML code.
    Your response absolutely MUST begin with the <thinking> block.
    """

    attempts = state.get("whyml_attempts", [])
    errors = state.get("errors", [])

    error_history_str = ""
    for i, (attempt, error) in enumerate(zip(attempts, errors)):
        error_history_str += f"--- ATTEMPT {i+1} ---\n"
        error_history_str += f"CODE:\n```whyml\n{attempt.strip()}\n```\n"
        error_history_str += f"ERROR:\n```text\n{error.strip()}\n```\n\n"

    final_prompt = ERROR_ANALYSIS_PROMPT.format(
        typed_python=state.get('typed_python', ''),
        error_history=error_history_str
    )

    response = llm.invoke([HumanMessage(content=final_prompt)])
    response_content = response.content

    thinking_match = re.search(r'<thinking>(.*?)</thinking>', response_content, re.DOTALL)
    thinking_text = thinking_match.group(1).strip() if thinking_match else "No thinking block found."

    corrected_whyml_code = clean_whyml_code(response_content)
    if corrected_whyml_code.strip().startswith("ml"):
        corrected_whyml_code = corrected_whyml_code.strip()[2:].strip()

    full_responses = state.get("full_responses", []) + [response_content]

    return {
        "messages": [AIMessage(content=corrected_whyml_code)],
        "retry_count": state.get("retry_count", 0) + 1,
        "conversion_timeout": False,
        "full_responses": full_responses
    }

def should_retry(state: State) -> str:
    """Decide whether to retry or end based on execution success and retry count"""
    if state.get("execution_success", False):
        return "end"
    elif state.get("retry_count", 0) >= 10:
        return "end"
    else:
        return "retry"

# Build the graph
graph_builder = StateGraph(State)

graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("whyml_converter", whyml_converter)
graph_builder.add_node("whyml_executor", whyml_executor)
graph_builder.add_node("error_corrector", error_corrector)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", "whyml_converter")
graph_builder.add_edge("whyml_converter", "whyml_executor")
graph_builder.add_conditional_edges(
    "whyml_executor",
    should_retry,
    {
        "retry": "error_corrector",
        "end": END
    }
)
graph_builder.add_edge("error_corrector", "whyml_executor")

graph = graph_builder.compile()

# Streamlit UI
st.title("Python to WhyML Converter")

# Input area
python_code = st.text_area(
    "Enter Python function:", 
    height=200,
    placeholder="def function_name(params):\n    # your code here"
)

if st.button("Convert to WhyML"):
    if python_code.strip():
        # Clear any previous state by reinitializing the graph
        graph_builder = StateGraph(State)
        
        graph_builder.add_node("chatbot", chatbot)
        graph_builder.add_node("whyml_converter", whyml_converter)
        graph_builder.add_node("whyml_executor", whyml_executor)
        graph_builder.add_node("error_corrector", error_corrector)
        
        graph_builder.add_edge(START, "chatbot")
        graph_builder.add_edge("chatbot", "whyml_converter")
        graph_builder.add_edge("whyml_converter", "whyml_executor")
        graph_builder.add_conditional_edges(
            "whyml_executor",
            should_retry,
            {
                "retry": "error_corrector",
                "end": END
            }
        )
        graph_builder.add_edge("error_corrector", "whyml_executor")
        
        graph = graph_builder.compile()
        
        with st.spinner("Converting to WhyML..."):
            # Initialize accumulated state
            accumulated_state = {
                "original_python": "",
                "typed_python": "",
                "whyml_attempts": [],
                "errors": [],
                "capability_gaps": [],
                "execution_success": False
            }
            
            # Process through the graph
            try:
                for event in graph.stream({"messages": [HumanMessage(content=python_code)]}):
                    for key, value in event.items():
                        accumulated_state.update(value)
                        
                        # Show progress
                        if "chatbot" in event:
                            st.info("Generated well-typed Python...")
                        elif "whyml_converter" in event:
                            st.info("Converting to WhyML...")
                        elif "whyml_executor" in event:
                            retry_count = accumulated_state.get("retry_count", 0)
                            if retry_count > 0:
                                st.info(f"Executing WhyML (Retry {retry_count})...")
                        elif "error_corrector" in event:
                            st.info("Analyzing errors and correcting...")
                            
            except Exception as e:
                st.error(f"Error during conversion: {str(e)}")
                st.stop()
            
            # Display results
            st.subheader("Results")
            
            # Show final WhyML code
            if accumulated_state.get("whyml_attempts"):
                final_whyml = accumulated_state["whyml_attempts"][-1]
                st.code(final_whyml, language="whyml")
                
                # Show success/failure status
                if accumulated_state.get("execution_success"):
                    st.success("WhyML code generated successfully!")
                else:
                    st.error("WhyML generation completed with errors")
            
            # Display capability gaps
            if accumulated_state.get("capability_gaps"):
                st.subheader("Capability Gaps Identified")
                for i, gap in enumerate(accumulated_state["capability_gaps"], 1):
                    st.write(f"**Attempt {i}:** {gap}")
            
            # Show number of attempts
            st.metric("Number of attempts", len(accumulated_state.get("whyml_attempts", [])))
            
            # Optional: Show detailed results in expander
            with st.expander("View detailed conversion history"):
                for i, (attempt, error) in enumerate(zip(
                    accumulated_state.get("whyml_attempts", []),
                    accumulated_state.get("errors", [])
                )):
                    st.write(f"**Attempt {i+1}:**")
                    st.code(attempt, language="whyml")
                    if error:
                        st.error(f"Error: {error}")
    else:
        st.warning("Please enter Python code to convert")