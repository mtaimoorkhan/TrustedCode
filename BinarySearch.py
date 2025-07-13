def binary_search(sorted_list, item_to_find):
    low = 0
    high = len(sorted_list) - 1
    while low <= high:
        mid = (low + high) // 2
        guess = sorted_list[mid]
        if guess == item_to_find:
            return mid
        if guess > item_to_find:
            high = mid - 1
        else:     
            low = mid + 1
            return None
