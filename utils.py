import re
import pandas as pd
from langchain_core.messages import SystemMessage, HumanMessage

from state import State
from config import llm, CAPABILITY_GAP_PROMPT

def clean_whyml_code(code: str) -> str:
    """Remove markdown code blocks and extra formatting from WhyML code"""
    # Remove markdown code blocks
    if "```" in code:
        # Match ```why or ```whyml or just ``` followed by code and closing ```
        pattern = r'```(?:why|whyml)?\s*\n?(.*?)```'
        match = re.search(pattern, code, re.DOTALL)
        if match:
            code = match.group(1).strip()
        else:
            # If no match, try to remove ``` lines
            lines = code.split('\n')
            cleaned_lines = [line for line in lines if not line.strip().startswith('```')]
            code = '\n'.join(cleaned_lines)

    # Remove any remaining backticks
    code = code.replace('`', '')

    # Remove lines that are clearly not WhyML code (like explanations)
    lines = code.split('\n')
    whyml_lines = []
    for line in lines:
        # Skip lines that look like explanations
        if line.strip() and not any(phrase in line.lower() for phrase in
                                  ['the code', 'here\'s', 'this is', 'the main', 'changes are',
                                   'looks correct', 'should compile', 'appears to be']):
            whyml_lines.append(line)

    return '\n'.join(whyml_lines).strip()


def classify_capability_gap(error_message: str) -> str:
    """Classify the error into capability gap categories"""
    if not error_message or error_message == "Timeout":
        return "N/A"

    # Create classification prompt
    system_msg = SystemMessage(content=CAPABILITY_GAP_PROMPT.format(error=error_message))
    human_msg = HumanMessage(content="Classify this error")

    try:
        response = llm.invoke([system_msg, human_msg])
        # Extract the full response (category + explanation)
        classification = response.content.strip()

        # Try to extract just the category code from the response
        valid_categories = ["PTyp", "TTyp", "STyp", "PSyn", "TSyn", "SSyn",
                            "PSem", "TSem", "SSem", "PKnow", "EKnow", "DKnow"]

        # Check if response starts with a valid category
        for category in valid_categories:
            if classification.startswith(category):
                return classification  # Return full response with explanation

        # If no valid category found at start, search in the response
        for category in valid_categories:
            if category in classification:
                return classification

        # Fallback classification based on keywords
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


def create_output_table(state: State):
    """Create output table with all collected data"""
    data = {
        "Original Python": [state.get("original_python", "")],
        "Well-typed Python": [state.get("typed_python", "")],
        "Number of Tries": [len(state.get("whyml_attempts", []))]
    }

    whyml_attempts = state.get("whyml_attempts", [])
    for i, attempt in enumerate(whyml_attempts):
        data[f"WhyML Attempt {i+1}"] = [attempt]

    errors = state.get("errors", [])
    for i, error in enumerate(errors):
        data[f"Error {i+1}"] = [error]

    capability_gaps = state.get("capability_gaps", [])
    for i, gap in enumerate(capability_gaps):
        data[f"Capability Gap {i+1}"] = [gap]

    df = pd.DataFrame(data)
    df.to_csv("whyml_conversion_results.csv", index=False)

    print("\n" + "="*120)
    print("CONVERSION RESULTS TABLE")
    print("="*120)

    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 40)

    print(df.to_string(index=False))
    print("="*120)
    print("Results saved to: whyml_conversion_results.csv")
    print("\nNote: Full content available in the CSV file")