def GCD(a: int, b: int) -> int:
    if b == 0:
        return a
    else:
        return GCD(b, a % b)
