def remove_negatives(nums):
    """Remove every negative number from nums in place and return nums."""
    for n in nums:
        if n < 0:
            nums.remove(n)
    return nums
