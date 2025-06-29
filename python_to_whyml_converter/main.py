import sys
from langchain_core.messages import HumanMessage
from graph_builder import build_graph
from utils import create_output_table


def stream_graph_updates(user_input: str, graph):
    """
    Streams the execution of the graph, prints live updates,
    and accumulates the final state.
    """
    print("Loaded Python Code:")
    print(user_input)
    print("-" * 50)

    # Initialize a dictionary to hold the final, accumulated state
    final_state = {}

    # Stream the graph execution
    for event in graph.stream(
        {"messages": [HumanMessage(content=user_input)]},
        stream_mode="updates"
    ):
        # The 'event' dictionary's key is the name of the node that just ran
        node_name = list(event.keys())[0]
        # The 'value' is the dictionary of outputs from that node
        node_output = event[node_name]

        # Print live updates
        if node_name == "chatbot":
            print("Well Typed Python Output: ")
        elif node_name == "whyml_translator":
            print("WhyML Specification: ")
        elif node_name == "whyml_executor":
            retry_count = final_state.get("retry_count", 0)
            if retry_count > 0:
                print(f"WhyML Execution Output (Retry {retry_count}): ")
            else:
                print("WhyML Execution Output: ")
        elif node_name == "error_corrector":
            print("Error Correction - Fixed WhyML: ")

        print(node_output["messages"][-1].content)
        print("-"*20)

        # Update the final state with the latest outputs
        final_state.update(node_output)

    # Create the final output table from the accumulated state
    create_output_table(final_state)


if __name__ == "__main__":
    # Build the graph
    graph = build_graph()

    # Attempt to save a visualization of the graph
    try:
        png_data = graph.get_graph().draw_mermaid_png()
        with open("graph_visualization.png", "wb") as f:
            f.write(png_data)
        print("\nGraph visualization saved to 'graph_visualization.png'.")
    except Exception as e:
        print(f"\nCould not save graph visualization: {e}")

    # Process input from a file specified as a command-line argument
    if len(sys.argv) < 2:
        print("\nUsage: python main.py <path_to_python_file.py>")
        sys.exit(1)
    
    try:
        input_file_path = sys.argv[1]
        with open(input_file_path, 'r') as f:
            user_input = f.read()
        
        print(f"\nProcessing file: {input_file_path}")
        print("-" * 50)
        stream_graph_updates(user_input, graph)
    
    except Exception as e:
        print(f"An error occurred: {e}")
        # Provide a default example if something goes wrong
        user_input = """def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    if count == 0:
        return 0.0
    return total / count"""
        print("\nRunning a default example instead...")
        stream_graph_updates(user_input, graph)