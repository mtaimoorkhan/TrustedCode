import os
import re
import subprocess
import tempfile
import threading
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from state import State
from utils import clean_whyml_code, classify_capability_gap
from config import (
    llm,
    TYPING_PROMPT,
    WHYML_PROMPT,
    ERROR_FIX_PROMPT,
    SAMPLE_WHYML_FILE,
)


def chatbot(state: State):
    system_msg = SystemMessage(content=TYPING_PROMPT)
    # Directly access the .content attribute.
    user_content = state["messages"][-1].content
    human_msg = HumanMessage(content=user_content)

    response = llm.invoke([system_msg, human_msg])

    # Store original and typed Python
    return {
        "messages": [response],
        "retry_count": 0,
        "original_python": user_content,
        "typed_python": response.content,
        "whyml_attempts": [],
        "errors": [],
        "capability_gaps": []
    }


def whyml_translator(state: State):
    print("whyml_translator function called!")

    # LangGraph only return changed fields.
    result = {
        "messages": [],
        "conversion_timeout": False,
    }

    def convert():
        try:
            # Create system message for WhyML conversion
            system_msg = SystemMessage(content=WHYML_PROMPT)
            # Get the typed Python code from previous step
            typed_code = state["messages"][-1].content
            human_msg = HumanMessage(content=typed_code)

            # Invoke LLM for WhyML conversion
            response = llm.invoke([system_msg, human_msg])

            # Clean the response to ensure no markdown formatting
            cleaned_content = clean_whyml_code(response.content)
            result["messages"] = [AIMessage(content=cleaned_content)]
        except Exception as e:
            result["messages"] = [HumanMessage(content=f"Conversion error: {str(e)}")]

    # Run conversion in a thread with timeout
    thread = threading.Thread(target=convert)
    thread.daemon = True
    thread.start()
    thread.join(timeout=20)  # 20 second timeout

    if thread.is_alive():
        print("WhyML conversion timed out after 20 seconds!")
        result["conversion_timeout"] = True
        result["messages"] = [HumanMessage(content="TIMEOUT: Using sample file instead")]

    return result


def whyml_executor(state: State):
    print("whyml_executor function called!")

    if state.get("conversion_timeout", False):
        print("Using sample WhyML file due to timeout...")
        try:
            with open(SAMPLE_WHYML_FILE, 'r') as f:
                whyml_code = f.read()
            print(f"Loaded sample file: {SAMPLE_WHYML_FILE}")
        except FileNotFoundError:
            return {
                "messages": [HumanMessage(content=f"Sample file '{SAMPLE_WHYML_FILE}' not found. Please create it or update the path.")],
                "execution_success": False
            }
    else:
        # The WhyML code was already cleaned in the previous node.
        whyml_code = state["messages"][-1].content

    #  Append and update list of steps.
    whyml_attempts = state.get("whyml_attempts", [])
    whyml_attempts.append(whyml_code)

    # Only return the fields that are being updated.
    state_update = {
        "whyml_code": whyml_code,
        "whyml_attempts": whyml_attempts,
    }

    # Create a temporary .mlw file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mlw', delete=False) as f:
        f.write(whyml_code)
        temp_filename = f.name

    try:
        # Execute WhyML using why3 command
        result = subprocess.run(['why3', 'prove', '-P', 'alt-ergo', temp_filename],
                                capture_output=True, text=True, timeout=30)

        output = f"WhyML Execution Result:\n"
        if state.get("conversion_timeout", False):
            output += f"(Using sample file: {SAMPLE_WHYML_FILE})\n"
        output += f"Return code: {result.returncode}\n"
        output += f"stdout:\n{result.stdout}\n"
        output += f"stderr:\n{result.stderr}"

        # Check if execution was successful (return code 0)
        state_update["execution_success"] = (result.returncode == 0)
        state_update["error_message"] = result.stderr if result.returncode != 0 else ""

        # Store error if failed
        if result.returncode != 0:
            errors = state.get("errors", [])
            errors.append(result.stderr)
            state_update["errors"] = errors

            # Classify capability gap
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
        # Clean up temporary file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

    state_update["messages"] = [response_msg]
    return state_update


def error_corrector(state: State):
    """
    Analyzes the history of errors and prompts the LLM to fix the root cause,
    avoiding repeated mistakes.
    """
    print("error_corrector function called!")

    # Error analysis prompt.
    ERROR_ANALYSIS_PROMPT = """You are an expert WhyML debugger and formal verification expert with PHD level mathematics knowledge. Your task is to fix a failing WhyML code translation by analyzing the complete history of attempts and errors to identify the root cause. You must not repeat past mistakes.  
    if you keep getting the same error after 2 tries, do not focus on the particular error, instead, focus on the error history and critically analyse the overarching problem you are trying to solve. Be precise, consistent, methodological and write minimal code that satisties the solution.  

    **Original Typed Python Code:**
    ```python
    {typed_python}
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

    # Building a clean, formatted history string so that the errors can be properly used by the LLM to minimise hallucinations.
    error_history_str = ""
    for i, (attempt, error) in enumerate(zip(attempts, errors)):
        error_history_str += f"--- ATTEMPT {i+1} ---\n"
        error_history_str += f"CODE:\n```whyml\n{attempt.strip()}\n```\n"
        error_history_str += f"ERROR:\n```text\n{error.strip()}\n```\n\n"

    # Use the single, more directive prompt with the full history.
    final_prompt = ERROR_ANALYSIS_PROMPT.format(
        typed_python=state.get('typed_python', ''),
        error_history=error_history_str
    )

    # Invoke the LLM.
    response = llm.invoke([HumanMessage(content=final_prompt)])
    response_content = response.content

    # Extract the "thinking" part for debugging and insight.
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', response_content, re.DOTALL)
    thinking_text = thinking_match.group(1).strip() if thinking_match else "No thinking block found."

    print("--- LLM Reasoning ---")
    print(thinking_text)
    print("--------------------")

    # Clean the response to get only the executable WhyML code.
    corrected_whyml_code = clean_whyml_code(response_content)
    if corrected_whyml_code.strip().startswith("ml"):
        print("Defensive cleaning: Removed erroneous 'ml' prefix.")
        corrected_whyml_code = corrected_whyml_code.strip()[2:].strip()

    # Preserve the full, detailed response from the LLM for the state.
    full_responses = state.get("full_responses", []) + [response_content]

    # Return the updated state for the graph.
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
    elif state.get("retry_count", 0) >= 10:  # Max 10 retries
        print("Max retries reached. Ending.")
        return "end"
    else:
        return "retry"