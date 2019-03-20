import numpy as np
from pystencils import make_slice
from lbmpy.boundaries import NoSlip, UBB
from lbmpy.scenarios import create_channel

try:
    import waLBerla as wLB
except ImportError:
    wLB = None


def calculate_force(step, obstacle):
    bh = step.boundary_handling
    bh.set_boundary(obstacle, make_slice[0.3:0.4, 0:0.5])
    step.run(100)
    return bh.force_on_boundary(obstacle)


def test_force_on_boundary():
    results = []
    domain_size = (80, 30)

    boundaries = [NoSlip('obstacle_noslip'),
                  UBB((0,) * len(domain_size), name='obstacle_UBB')]

    for parallel in (False, True) if wLB else (False,):
        for boundary_obj in boundaries:
            print("Testing parallel %d, boundary %s" % (parallel, boundary_obj.name))
            step = create_channel(domain_size, force=1e-5, relaxation_rate=1.5, parallel=parallel, force_model='buick')
            force = calculate_force(step, boundary_obj)
            print("  -> force = ", force)
            results.append(force)

    for res in results[1:]:
        np.testing.assert_almost_equal(results[0], res)
