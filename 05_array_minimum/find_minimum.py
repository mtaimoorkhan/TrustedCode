from typing import List, Union, Tuple

def find_minimum(arr: List[Union[int, float]]) -> Union[int, float]:
    if not arr:
        raise ValueError("Array cannot be empty")
    
    # Initialize minimum with the first element
    minimum: Union[int, float] = arr[0]
    
    # Iterate through the rest of the array
    for i in range(1, len(arr)):
        if arr[i] < minimum:
            minimum = arr[i]
    
    return minimum
