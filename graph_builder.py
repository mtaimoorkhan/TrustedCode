from langgraph.graph import StateGraph, START, END
from state import State
from graph_nodes import (
    chatbot,
    whyml_translator,
    whyml_executor,
    error_corrector,
    should_retry
)

def build_graph():
    """
    Builds and compiles the LangGraph state machine.
    """
    graph_builder = StateGraph(State)

    # Add all the nodes to the graph
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("whyml_translator", whyml_translator)
    graph_builder.add_node("whyml_executor", whyml_executor)
    graph_builder.add_node("error_corrector", error_corrector)

    # Define the graph's execution flow (edges)
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_edge("chatbot", "whyml_translator")
    graph_builder.add_edge("whyml_translator", "whyml_executor")

    # Add a conditional edge for the retry loop
    graph_builder.add_conditional_edges(
        "whyml_executor",
        should_retry,
        {
            "retry": "error_corrector",
            "end": END
        }
    )
    graph_builder.add_edge("error_corrector", "whyml_executor")

    # Compile the graph
    graph = graph_builder.compile()
    return graph