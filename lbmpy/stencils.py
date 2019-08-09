def get_stencil(name, ordering='walberla'):
    """
    Stencils are tuples of discrete velocities. They are commonly labeled in the 'DxQy' notation, where d is the
    dimension (length of the velocity tuples) and y is number of discrete velocities.

    Args:
        name: DxQy notation
        ordering: the LBM literature does not use a common order of the discrete velocities, therefore here
                  different common orderings are available. All orderings lead to the same method, it just has
                  to be used consistently. Here more orderings are available to compare intermediate results with
                  the literature.
    """
    try:
        return get_stencil.data[name.upper()][ordering.lower()]
    except KeyError:
        err_msg = ""
        for stencil, ordering_names in get_stencil.data.items():
            err_msg += "  %s: %s\n" % (stencil, ", ".join(ordering_names.keys()))

        raise ValueError("No such stencil available. "
                         "Available stencils: <stencil_name>( <ordering_names> )\n" + err_msg)


get_stencil.data = {
    'D2Q9': {
        'walberla': ((0, 0),
                     (0, 1), (0, -1), (-1, 0), (1, 0),
                     (-1, 1), (1, 1), (-1, -1), (1, -1),),
        'counterclockwise': ((0, 0),
                             (1, 0), (0, 1), (-1, 0), (0, -1),
                             (1, 1), (-1, 1), (-1, -1), (1, -1)),
        'braunschweig': ((0, 0),
                         (-1, 1), (-1, 0), (-1, -1), (0, -1),
                         (1, -1), (1, 0), (1, 1), (0, 1)),
        'uk': ((0, 0),
               (1, 0), (-1, 0), (0, 1), (0, -1),
               (1, 1), (-1, -1), (-1, 1), (1, -1),
               )
    },
    'D3Q15': {
        'walberla':
            ((0, 0, 0),
             (0, 1, 0), (0, -1, 0), (-1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, -1),
             (1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1), (1, 1, -1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1)),
        'premnath': ((0, 0, 0),
                     (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                     (1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1),
                     (1, 1, -1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1)),
    },
    'D3Q19': {
        'walberla': ((0, 0, 0),
                     (0, 1, 0), (0, -1, 0), (-1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, -1),
                     (-1, 1, 0), (1, 1, 0), (-1, -1, 0), (1, -1, 0),
                     (0, 1, 1), (0, -1, 1), (-1, 0, 1), (1, 0, 1),
                     (0, 1, -1), (0, -1, -1), (-1, 0, -1), (1, 0, -1)),
        'braunschweig': ((0, 0, 0),
                         (1, 0, 0), (-1, 0, 0),
                         (0, 1, 0), (0, -1, 0),
                         (0, 0, 1), (0, 0, -1),
                         (1, 1, 0), (-1, -1, 0),
                         (1, -1, 0), (-1, 1, 0),
                         (1, 0, 1), (-1, 0, -1),
                         (1, 0, -1), (-1, 0, 1),
                         (0, 1, 1), (0, -1, -1),
                         (0, 1, -1), (0, -1, 1)),
        'premnath': ((0, 0, 0),
                     (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                     (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
                     (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
                     (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1)),
    },
    'D3Q27': {
        'walberla': ((0, 0, 0),
                     (0, 1, 0), (0, -1, 0), (-1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, -1),
                     (-1, 1, 0), (1, 1, 0), (-1, -1, 0), (1, -1, 0),
                     (0, 1, 1), (0, -1, 1), (-1, 0, 1), (1, 0, 1),
                     (0, 1, -1), (0, -1, -1), (-1, 0, -1), (1, 0, -1),
                     (1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1), (1, 1, -1), (-1, 1, -1), (1, -1, -1),
                     (-1, -1, -1)),
        'premnath': ((0, 0, 0),
                     (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                     (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
                     (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
                     (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1),
                     (1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1),
                     (1, 1, -1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1))
    }
}
