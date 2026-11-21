def count_vowels(text):
    """Return how many vowels (a, e, i, o, u) are in text, ignoring case."""
    count = 0
    for ch in text:
        if ch.lower() in "aeiou":
            count += 1
    return count
