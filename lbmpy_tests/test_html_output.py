from lbmpy.creationfunctions import create_lb_method
from lbmpy.methods.creationfunctions import compare_moment_based_lb_methods
from lbmpy.moments import (
    moment_equality_table, moment_equality_table_by_stencil, moments_up_to_component_order)
from lbmpy.stencils import get_stencil


def test_moment_comparison_table():
    new = create_lb_method(stencil='D3Q19', maxwellian_moments=True)
    old = create_lb_method(stencil='D3Q19', maxwellian_moments=False)

    assert old.zeroth_order_equilibrium_moment_symbol == new.zeroth_order_equilibrium_moment_symbol

    assert '<td' in new._repr_html_()

    res_deviations_only = compare_moment_based_lb_methods(old, new, show_deviations_only=True)
    assert len(res_deviations_only.array) == 4

    res_all = compare_moment_based_lb_methods(old, new, show_deviations_only=False)
    assert len(res_all.array) == 20

    d3q27 = create_lb_method(stencil='D3Q27')
    compare_moment_based_lb_methods(d3q27, new, show_deviations_only=False)
    compare_moment_based_lb_methods(new, d3q27, show_deviations_only=False)


def test_moment_equality_table():
    d3q19 = get_stencil('D3Q19')
    table1 = moment_equality_table(d3q19, max_order=3)
    assert len(table1.array) == 5

    table2 = moment_equality_table_by_stencil({'D3Q19': d3q19, 'D3Q27': get_stencil("D3Q27")},
                                              moments_up_to_component_order(2, dim=3))
    assert len(table2.array) == 11
    assert len(table2.array[0]) == 2 + 2
