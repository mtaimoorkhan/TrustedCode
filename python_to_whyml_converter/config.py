import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

# Load environment variables from .env file
load_dotenv()

# Initialize the language model
llm = ChatAnthropic(model='claude-sonnet-4-20250514', temperature=0.1)

# Prompt for converting Python to well-typed Python
TYPING_PROMPT = """Convert the code provided into well-typed python code. add type hints in the function such as int or float as relevant. import relevant libraries as you see fit. You must output raw Python code only. Start directly with 'def' or 'class'. No formatting."""

# Prompt for converting typed Python to WhyML
WHYML_PROMPT = """You are an expert in formal verification using Why3. Convert the following well typed Python function into WhyML. Do NOT use markdown formatting or code blocks. Output only raw WhyML code. start with module and end blocks. import relevant libraries as you see fit."""

# Prompt for fixing WhyML code based on errors
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

# Prompt for classifying Why3 capability gaps
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

# Constants
SAMPLE_WHYML_FILE = "sample.mlw"