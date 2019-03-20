import os
import numpy as np
from tempfile import TemporaryDirectory
from lbmpy.scenarios import create_lid_driven_cavity
import lbmpy.plot2d as plt


def test_animation():

    ldc = create_lid_driven_cavity((10, 10), relaxation_rate=1.8)

    def run_vec():
        ldc.run(100)
        return ldc.velocity[:, :, :]

    def run_scalar():
        ldc.run(100)
        return ldc.density[:, :]

    plt.clf()
    plt.cla()

    with TemporaryDirectory() as tmp_dir:
        ani = plt.vector_field_magnitude_animation(run_vec, interval=1, frames=30)
        ani.save(os.path.join(tmp_dir, "animation1.avi"))

        ani = plt.vector_field_animation(run_vec, interval=1, frames=30, rescale=True)
        ani.save(os.path.join(tmp_dir, "animation2.avi"))

        ani = plt.vector_field_animation(run_vec, interval=1, frames=30, rescale=False)
        ani.save(os.path.join(tmp_dir, "animation3.avi"))

        ani = plt.scalar_field_animation(run_scalar, interval=1, frames=30, rescale=True)
        ani.save(os.path.join(tmp_dir, "animation4.avi"))

        ani = plt.scalar_field_animation(run_scalar, interval=1, frames=30, rescale=False)
        ani.save(os.path.join(tmp_dir, "animation5.avi"))

        ani = plt.surface_plot_animation(run_scalar, frames=30)
        ani.save(os.path.join(tmp_dir, "animation6.avi"))


def test_plot():
    arr = np.ones([3, 3, 2])
    plt.multiple_scalar_fields(arr)
    plt.show()
