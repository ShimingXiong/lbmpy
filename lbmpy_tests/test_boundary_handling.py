import numpy as np
import pytest

from lbmpy.boundaries import UBB, NeumannByCopy, NoSlip, StreamInConstant
from lbmpy.boundaries.boundaryhandling import LatticeBoltzmannBoundaryHandling
from lbmpy.creationfunctions import create_lb_function
from lbmpy.geometry import add_box_boundary
from lbmpy.lbstep import LatticeBoltzmannStep
from pystencils import create_data_handling, make_slice


@pytest.mark.parametrize("target", ['cpu', 'gpu', 'opencl'])
def test_simple(target):
    if target == 'gpu':
        import pytest
        pytest.importorskip('pycuda')
    elif target == 'opencl':
        import pytest
        pytest.importorskip('pyopencl')
        import pystencils.opencl.autoinit

    dh = create_data_handling((10, 5), parallel=False, default_target=target)
    dh.add_array('pdfs', values_per_cell=9, cpu=True, gpu=target!='cpu')
    lb_func = create_lb_function(stencil='D2Q9',
                                 compressible=False,
                                 relaxation_rate=1.8,
                                 optimization={'target': target})

    bh = LatticeBoltzmannBoundaryHandling(lb_func.method, dh, 'pdfs', target=target)

    wall = NoSlip()
    moving_wall = UBB((0.001, 0))
    bh.set_boundary(wall, make_slice[0, :])
    bh.set_boundary(wall, make_slice[-1, :])
    bh.set_boundary(wall, make_slice[:, 0])
    bh.set_boundary(moving_wall, make_slice[:, -1])

    bh.prepare()
    bh()


def test_exotic_boundaries():
    step = LatticeBoltzmannStep((50, 50), relaxation_rate=1.8, compressible=False, periodicity=False)
    add_box_boundary(step.boundary_handling, NeumannByCopy())
    step.boundary_handling.set_boundary(StreamInConstant(0), make_slice[0, :])
    step.run(100)
    assert np.max(step.velocity[:, :, :]) < 1e-13
