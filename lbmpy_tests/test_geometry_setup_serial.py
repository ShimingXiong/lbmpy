import os

import numpy as np

from lbmpy.boundaries import NoSlip
from lbmpy.geometry import add_black_and_white_image, add_pipe_walls
from lbmpy.lbstep import LatticeBoltzmannStep
from pystencils.slicing import make_slice


def test_pipe():
    """Ensures that pipe can be set up in 2D, 3D, with constant and callback diameter
    No tests are done that geometry is indeed correct"""

    def diameter_callback(x, domain_shape):
        d = domain_shape[1]
        y = np.ones_like(x) * d

        y[x > 0.5 * domain_shape[0]] = int(0.3 * d)
        return y

    plot = False
    for domain_size in [(30, 10, 10), (30, 10)]:
        for diameter in [5, 10, diameter_callback]:
            sc = LatticeBoltzmannStep(domain_size=domain_size, method='srt', relaxation_rate=1.9,
                                      optimization={})
            add_pipe_walls(sc.boundary_handling, diameter)
            if plot:
                import lbmpy.plot as plt
                from pystencils.slicing import make_slice
                if len(domain_size) == 2:
                    plt.boundary_handling(sc.boundary_handling)
                    plt.title("2D, diameter=%s" % (str(diameter,)))
                    plt.show()
                elif len(domain_size) == 3:
                    plt.subplot(1, 2, 1)
                    plt.boundary_handling(sc.boundary_handling, make_slice[0.5, :, :])
                    plt.title("3D, diameter=%s" % (str(diameter,)))
                    plt.subplot(1, 2, 2)
                    plt.boundary_handling(sc.boundary_handling, make_slice[:, 0.5, :])
                    plt.title("3D, diameter=%s" % (str(diameter, )))
                    plt.show()


def get_test_image_path():
    script_file = os.path.realpath(__file__)
    script_dir = os.path.dirname(script_file)
    return os.path.join(script_dir, 'testImage.png')


def test_image():
    sc = LatticeBoltzmannStep(domain_size=(50, 40), method='srt', relaxation_rate=1.9,
                              optimization={})
    add_black_and_white_image(sc.boundary_handling, get_test_image_path(), keep_aspect_ratio=True)


def test_slice_mask_combination():
    sc = LatticeBoltzmannStep(domain_size=(30, 30), method='srt', relaxation_rate=1.9,
                              optimization={})

    def callback(*coordinates):
        x = coordinates[0]
        print("x", coordinates[0][:, 0])
        print("y", coordinates[1][0, :])
        print(x.shape)
        return np.ones_like(x, dtype=np.bool)

    sc.boundary_handling.set_boundary(NoSlip(), make_slice[6:7, -1], callback)
