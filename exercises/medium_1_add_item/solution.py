def add_item(item, items=None):
    """Return a list that contains item.

    If items is given, add item to it. If it is not given, start a new list.
    """
    if items is None:
        items = []
    items.append(item)
    return items
