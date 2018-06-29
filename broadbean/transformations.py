from copy import copy

def get_transformed_context(input_context,
                            transformation: callable):
    new_context = copy(input_context)
    if transformation:
        transformation(new_context)
    return new_context

