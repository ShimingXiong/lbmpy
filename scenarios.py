"""
Scenario setup
==============

This module contains functions to set up pre-defined scenarios like a lid-driven cavity or channel flows.
It is a good starting point if you are new to lbmpy.

>>> scenario = create_channel(domain_size=(20, 10), force=1e-5,
...                          method='srt', relaxation_rate=1.9)
>>> scenario.run(100)

All scenarios can be modified, for example you can create a simple channel first, then place an object in it:

>>> from lbmpy.boundaries import NoSlip
>>> from pystencils.slicing import makeSlice
>>> flag = scenario.boundary_handling.set_boundary(NoSlip(), makeSlice[0.3:0.4, 0.0:0.3])



Functions for scenario setup:
-----------------------------

All of the following scenario creation functions take keyword arguments specifying which LBM method should be used
and a ``optimization`` dictionary, defining performance related options. These parameters are documented
at :mod:`lbmpy.creationfunctions`. The only mandatory keyword parameter is ``relaxation_rate``,
that defines the viscosity of the fluid (valid values being between 0 and 2).
"""
import numpy as np
from lbmpy.geometry import setup_channel_walls, add_parabolic_velocity_inflow
from lbmpy.lbstep import LatticeBoltzmannStep
from pystencils.datahandling import create_data_handling
from pystencils.slicing import slice_from_direction
from lbmpy.boundaries import NoSlip, UBB, FixedDensity


def create_fully_periodic_flow(initial_velocity, periodicity_in_kernel=False, lbm_kernel=None,
                               data_handling=None, parallel=False, **kwargs):
    """Creates a fully periodic setup with prescribed velocity field.

    Args:
        initial_velocity: numpy array that defines an initial velocity for each cell. The shape of this
                         array determines the domain size.
        periodicity_in_kernel: don't use boundary handling for periodicity, but directly generate the kernel periodic
        lbm_kernel: a LBM function, which would otherwise automatically created
        data_handling: data handling instance that is used to create the necessary fields. If a data handling is
                       passed the periodicity and parallel arguments are ignored.
        parallel: True for distributed memory parallelization with walberla
        kwargs: other parameters are passed on to the method, see :mod:`lbmpy.creationfunctions`

    Returns:
        instance of :class:`Scenario`
    """
    if 'optimization' not in kwargs:
        kwargs['optimization'] = {}
    else:
        kwargs['optimization'] = kwargs['optimization'].copy()
    domain_size = initial_velocity.shape[:-1]
    if periodicity_in_kernel:
        kwargs['optimization']['builtin_periodicity'] = (True, True, True)

    if data_handling is None:
        data_handling = create_data_handling(parallel, domain_size, periodicity=not periodicity_in_kernel,
                                             default_ghost_layers=1)
    step = LatticeBoltzmannStep(data_handling=data_handling, name="periodicScenario", lbm_kernel=lbm_kernel, **kwargs)
    for b in step.data_handling.iterate(ghost_layers=False):
        np.copyto(b[step.velocity_data_name], initial_velocity[b.global_slice])
    step.set_pdf_fields_from_macroscopic_values()
    return step


def create_lid_driven_cavity(domain_size=None, lid_velocity=0.005, lbm_kernel=None, parallel=False,
                             data_handling=None, **kwargs):
    """Creates a lid driven cavity scenario.

    Args:
        domain_size: tuple specifying the number of cells in each dimension
        lid_velocity: x velocity of lid in lattice coordinates.
        lbm_kernel: a LBM function, which would otherwise automatically created
        kwargs: other parameters are passed on to the method, see :mod:`lbmpy.creationfunctions`
        parallel: True for distributed memory parallelization with walberla
        data_handling: see documentation of :func:`create_fully_periodic_flow`
    Returns:
        instance of :class:`Scenario`
    """
    assert domain_size is not None or data_handling is not None
    if data_handling is None:
        data_handling = create_data_handling(parallel, domain_size, periodicity=False, default_ghost_layers=1)
    step = LatticeBoltzmannStep(data_handling=data_handling, lbm_kernel=lbm_kernel, name="lidDrivenCavity", **kwargs)

    my_ubb = UBB(velocity=[lid_velocity, 0, 0][:step.method.dim])
    step.boundary_handling.set_boundary(my_ubb, slice_from_direction('N', step.dim))
    for direction in ('W', 'E', 'S') if step.dim == 2 else ('W', 'E', 'S', 'T', 'B'):
        step.boundary_handling.set_boundary(NoSlip(), slice_from_direction(direction, step.dim))

    return step


def create_channel(domain_size=None, force=None, pressure_difference=None, u_max=None, diameter_callback=None,
                   duct=False, wall_boundary=NoSlip(), parallel=False, data_handling=None, **kwargs):
    """Create a channel scenario (2D or 3D).
    
    :param domain_size: size of the simulation domain. First coordinate is the flow direction.
    
    The channel can be driven by one of the following methods. Please specify exactly one of the following parameters: 
    :param force: Periodic channel, driven by a body force. Pass force in flow direction in lattice units here.
    :param pressure_difference: Inflow and outflow are fixed pressure conditions, with the given pressure difference. 
    :param u_max: Parabolic velocity profile prescribed at inflow, pressure boundary =1.0 at outflow.
    
    Geometry parameters:
    :param diameter_callback: optional callback for channel with varying diameters. Only valid if duct=False.
                             The callback receives x coordinate array and domain_size and returns a
                             an array of diameters of the same shape
    :param duct: if true the channel has rectangular instead of circular cross section
    :param wall_boundary: instance of boundary class that should be set at the channel walls
    :param parallel: True for distributed memory parallelization with walberla
    :param data_handling: see documentation of :func:`create_fully_periodic_flow`
    :param kwargs: all other keyword parameters are passed directly to scenario class.
    """
    assert domain_size is not None or data_handling is not None

    if [bool(p) for p in (force, pressure_difference, u_max)].count(True) != 1:
        raise ValueError("Please specify exactly one of the parameters 'force', 'pressure_difference' or 'u_max'")

    periodicity = (True, False, False) if force else (False, False, False)
    if data_handling is None:
        dim = len(domain_size)
        assert dim in (2, 3)
        data_handling = create_data_handling(parallel, domain_size, periodicity=periodicity[:dim],
                                             default_ghost_layers=1)

    dim = data_handling.dim
    if force:
        kwargs['force'] = tuple([force, 0, 0][:dim])
        assert data_handling.periodicity[0]
        step = LatticeBoltzmannStep(data_handling=data_handling, name="forceDrivenChannel", **kwargs)
    elif pressure_difference:
        inflow = FixedDensity(1.0 + pressure_difference)
        outflow = FixedDensity(1.0)
        step = LatticeBoltzmannStep(data_handling=data_handling, name="pressureDrivenChannel", **kwargs)
        step.boundary_handling.set_boundary(inflow, slice_from_direction('W', dim))
        step.boundary_handling.set_boundary(outflow, slice_from_direction('E', dim))
    elif u_max:
        if duct:
            raise NotImplementedError("Velocity inflow for duct flows not yet implemented")
        step = LatticeBoltzmannStep(data_handling=data_handling, name="velocityDrivenChannel", **kwargs)
        diameter = diameter_callback(np.array([0]), domain_size)[0] if diameter_callback else min(domain_size[1:])
        add_parabolic_velocity_inflow(step.boundary_handling, u_max, slice_from_direction('W', dim),
                                      vel_coord=0, diameter=diameter)
        outflow = FixedDensity(1.0)
        step.boundary_handling.set_boundary(outflow, slice_from_direction('E', dim))
    else:
        assert False

    setup_channel_walls(step.boundary_handling, diameter_callback, duct, wall_boundary)
    return step

