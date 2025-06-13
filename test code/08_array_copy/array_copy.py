def lcopy(xs: list[int]) -> list[int]:
    res: list[int] = [0] * len(xs)
    i: int
    for i in range(len(xs)):
        res[i] = xs[i]
    return res
