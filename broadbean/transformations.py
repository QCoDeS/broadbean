from functools import wraps


# wrapper for transformations
def transformation(trans_func):
    @wraps(trans_func)
    def inner(inp_dict):
        result = trans_func(inp_dict.copy())
        return result
    return inner
