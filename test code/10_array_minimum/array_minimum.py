from typing import List

def find_minimum(arr: List[int]) -> int:
    min_val: int = arr[0]
    for i in range(1, len(arr)):
        if arr[i] < min_val:
            min_val = arr[i]
    return min_val
