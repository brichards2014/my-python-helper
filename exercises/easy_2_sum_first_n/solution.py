def sum_first_n(nums, n):
    """Return the sum of the first n items in nums. If n is larger than the list, sum every item."""
    total = 0
    for i in range(n):
        if i < len(nums):
            total += nums[i]
    return total
