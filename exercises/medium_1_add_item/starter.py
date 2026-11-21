def add_item(item, items=[]):
    """Return a list that contains item.

    If items is given, add item to it. If it is not given, start a new list.
    """
    items.append(item)
    return items
