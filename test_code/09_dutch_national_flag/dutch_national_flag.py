from typing import List, Optional

def dutch_national_flag(arr: Optional[List[int]]) -> None:
    if not arr:
        return
    
    low: int = 0
    mid: int = 0
    high: int = len(arr) - 1
    
    while mid <= high:
        if arr[mid] == 0:
            arr[low], arr[mid] = arr[mid], arr[low]
            low += 1
            mid += 1
        elif arr[mid] == 1:
            mid += 1
        else:
            arr[mid], arr[high] = arr[high], arr[mid]
            high -= 1
