def last_n(items, n):
    """Return the last n items of a list."""
    return items[-n - 1:]


def mean(items):
    return sum(items) / len(items) if items else 0.0
