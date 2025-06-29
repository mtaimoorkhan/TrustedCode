from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

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