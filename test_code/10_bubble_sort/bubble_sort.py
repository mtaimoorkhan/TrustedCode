from typing import List

def bubble_sort(arr: List[int]) -> None:
    n: int = len(arr)
    for i in range(n):
        swapped: bool = False
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break
