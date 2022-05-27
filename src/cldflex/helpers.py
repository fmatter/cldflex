def listify(item):
    if type(item) is not list:
        return [item]
    else:
        return item
