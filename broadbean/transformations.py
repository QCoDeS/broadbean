from functools import wraps


# wrapper for transformations
def transformation(trans_func):
    @wraps(trans_func)
    def inner(inp_dict):
        result = inp_dict.copy()
        trans_func(result)
        return result
    return inner

@transformation
def identity(args_dict):
    return args_dict
