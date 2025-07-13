def find_minimum(arr):
    if not arr:
        raise ValueError("Array cannot be empty")
    
    # Initialize minimum with the first element
    minimum = arr[0]
    
    # Iterate through the rest of the array
    for i in range(1, len(arr)):
        if arr[i] < minimum:
            minimum = arr[i]
    
    return minimum
