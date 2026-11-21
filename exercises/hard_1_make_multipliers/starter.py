def make_multipliers(n):
    """Return a list of n functions. The function at index i multiplies its argument by i."""
    funcs = []
    for i in range(n):
        funcs.append(lambda x: x * i)
    return funcs
