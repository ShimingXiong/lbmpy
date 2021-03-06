"""Scenario that simulates a channel with a narrow area to analyse the rotational symmetry of the flow field.

This setup is used to illustrate the difference of D3Q19 and D3Q27 for high Reynolds number flows as shown in
    "Rotational invariance in the three-dimensional lattice Boltzmann method is dependent on the choice of lattice" by
    Alexander Thomas White, Chuh Khiun Chong (2011)

The deficiencies of the D3Q19 model can be resolved by choosing a better equilibrium (D3Q19_new)
"""
import os
import sys

import numpy as np
import sympy as sp

from lbmpy.boundaries import FixedDensity, NoSlip
from lbmpy.geometry import add_pipe_inflow_boundary, add_pipe_walls
from lbmpy.lbstep import LatticeBoltzmannStep
from lbmpy.relaxationrates import relaxation_rate_from_lattice_viscosity
from pystencils import create_data_handling
from pystencils.slicing import make_slice, slice_from_direction


def rod_simulation(stencil_name, diameter, parallel=False, entropic=False, re=150,
                   time_to_simulate=17.0, eval_interval=0.5, write_vtk=True, write_numpy=True,
                   optimization_params=None):
    if optimization_params is None:
        optimization_params = {}

    if stencil_name == 'D3Q19_new':
        stencil = 'D3Q19'
        maxwellian_moments = True
    elif stencil_name == 'D3Q19_old':
        stencil = 'D3Q19'
        maxwellian_moments = False
    elif stencil_name == 'D3Q27':
        stencil = 'D3Q27'
        maxwellian_moments = False
    else:
        raise ValueError("Unknown stencil name " + stencil_name)
    d = diameter
    length = 16 * d

    u_max_at_throat = 0.07
    u_max_at_inflow = 0.07 / (3 ** 2)

    # Geometry parameters
    inflow_area = int(1.5 * d)
    constriction_length = int(1.8904 * d)
    throat_length = int(10 / 3 * d)
    constriction_diameter = int(d / 3)

    u_mean_at_throat = u_max_at_throat / 2
    lattice_viscosity = u_mean_at_throat * constriction_diameter / re
    omega = relaxation_rate_from_lattice_viscosity(lattice_viscosity)

    method_parameters = {'stencil': stencil,
                         'compressible': True,
                         'method': 'srt',
                         'relaxation_rates': [omega],
                         'entropic': entropic,
                         'maxwellian_moments': maxwellian_moments, }
    kernel_params = {}
    if entropic:
        method_parameters['method'] = 'mrt3'
        method_parameters['relaxation_rates'] = sp.symbols("omega_fix omega_fix omega_free")
        kernel_params['omega_fix'] = omega

    print("ω=", omega)

    dh = create_data_handling(domain_size=(length, d, d), parallel=parallel)
    sc = LatticeBoltzmannStep(data_handling=dh, kernel_params=kernel_params, optimization=optimization_params,
                              name=stencil_name, **method_parameters)

    # -----------------   Boundary Setup   --------------------------------

    def pipe_geometry(x, *_):
        # initialize with full diameter everywhere
        result = np.ones_like(x) * d

        # constriction
        constriction_begin = inflow_area
        constriction_end = constriction_begin + constriction_length
        c_x = np.linspace(0, 1, constriction_length)
        result[constriction_begin: constriction_end] = d * (1 - c_x) + constriction_diameter * c_x

        # throat
        throat_start = constriction_end
        throat_end = throat_start + throat_length
        result[throat_start: throat_end] = constriction_diameter

        return result

    bh = sc.boundary_handling
    add_pipe_inflow_boundary(bh, u_max_at_inflow, make_slice[0, :, :])
    outflow = FixedDensity(1.0)
    bh.set_boundary(outflow, slice_from_direction('E', 3))
    wall = NoSlip()
    add_pipe_walls(bh, pipe_geometry, wall)

    # -----------------   Run  --------------------------------------------

    scenario_name = stencil_name
    if entropic:
        scenario_name += "_entropic"

    if not os.path.exists(scenario_name):
        os.mkdir(scenario_name)

    def to_time_steps(non_dimensional_time):
        return int(diameter / (u_max_at_inflow / 2) * non_dimensional_time)

    time_steps = to_time_steps(time_to_simulate)
    eval_interval = to_time_steps(eval_interval)

    print("Total number of time steps", time_steps)

    for i in range(time_steps // eval_interval):
        sc.run(eval_interval)
        if write_vtk:
            sc.write_vtk()
        vel = sc.velocity[:, :, :, :]
        max_vel = np.max(vel)
        print("Time steps:", sc.time_steps_run,  "/",  time_steps, "Max velocity: ", max_vel)
        if np.isnan(max_vel):
            raise ValueError("Simulation went unstable")
        if write_numpy:
            np.save(scenario_name + '/velocity_%06d' % (sc.time_steps_run,), sc.velocity_slice().filled(0.0))


def test_rod_scenario_simple():
    rod_simulation("D3Q19_new", re=100, diameter=20, parallel=False, entropic=False,
                   time_to_simulate=0.2, eval_interval=0.1, write_vtk=False, write_numpy=False)


if __name__ == '__main__':
    # High Re (Entropic method)
    rod_simulation(stencil_name=sys.argv[1], re=500, diameter=80, entropic=True, time_to_simulate=17,
                   parallel=False, optimization_params={'target': 'gpu'})
