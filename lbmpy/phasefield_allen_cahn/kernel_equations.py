from pystencils.field import Field
from lbmpy.creationfunctions import update_with_default_parameters
from lbmpy.fieldaccess import StreamPushTwoFieldsAccessor, CollideOnlyInplaceAccessor
from pystencils.fd.derivation import FiniteDifferenceStencilDerivation
from lbmpy.maxwellian_equilibrium import get_weights
from pystencils import Assignment, AssignmentCollection
from lbmpy.phasefield_allen_cahn.derivatives import laplacian, isotropic_gradient

import sympy as sp
import numpy as np


def chemical_potential_symbolic(phi_field, stencil, beta, kappa):
    r"""
    Get a symbolic expression for the chemical potential according to equation (5) in PhysRevE.96.053301.
    Args:
        phi_field: the phase-field on which the chemical potential is applied
        stencil: stencil of the lattice Boltzmann step
        beta: coefficient related to surface tension and interface thickness
        kappa: coefficient related to surface tension and interface thickness
    """
    dimensions = len(stencil[0])

    deriv = FiniteDifferenceStencilDerivation((0, 0), stencil)
    # assume the stencil is symmetric
    deriv.assume_symmetric(0)
    deriv.assume_symmetric(1)
    if dimensions == 3:
        deriv.assume_symmetric(2)

    # set weights for missing degrees of freedom in the calculation
    if len(stencil) == 9:
        deriv.set_weight((1, 1), sp.Rational(1, 6))
        deriv.set_weight((0, -1), sp.Rational(2, 3))
        deriv.set_weight((0, 0), sp.Rational(-10, 3))

        # assume the stencil is isotropic
        res = deriv.get_stencil(isotropic=True)
        lap = res.apply(phi_field.center)
    else:
        lap = laplacian(phi_field)

    # get the chemical potential
    mu = 4.0 * beta * phi_field.center * (phi_field.center - 1.0) * (phi_field.center - 0.5) - \
        kappa * lap
    return mu


def isotropic_gradient_symbolic(phi_field, stencil):
    r"""
    Get a symbolic expression for the isotropic gradient of the phase-field
    Args:
        phi_field: the phase-field on which the isotropic gradient is applied
        stencil: stencil of the lattice Boltzmann step
    """
    dimensions = len(stencil[0])
    deriv = FiniteDifferenceStencilDerivation((0,), stencil)

    deriv.assume_symmetric(0, anti_symmetric=True)
    deriv.assume_symmetric(1, anti_symmetric=False)
    if dimensions == 3:
        deriv.assume_symmetric(2, anti_symmetric=False)

    if len(stencil) == 9:
        res = deriv.get_stencil(isotropic=True)
        grad = [res.apply(phi_field.center), res.rotate_weights_and_apply(phi_field.center, (0, 1)), 0]
    elif len(stencil) == 19:
        deriv.set_weight((0, 0, 0), sp.Integer(0))
        deriv.set_weight((1, 0, 0), sp.Rational(1, 6))
        deriv.set_weight((1, 1, 0), sp.Rational(1, 12))

        res = deriv.get_stencil(isotropic=True)
        grad = [res.apply(phi_field.center),
                res.rotate_weights_and_apply(phi_field.center, (1, 0)),
                res.rotate_weights_and_apply(phi_field.center, (2, 1))]
    else:
        grad = isotropic_gradient(phi_field)

    return grad


def normalized_isotropic_gradient_symbolic(phi_field, stencil):
    r"""
    Get a symbolic expression for the normalized isotropic gradient of the phase-field
    Args:
        phi_field: the phase-field on which the normalized isotropic gradient is applied
        stencil: stencil of the lattice Boltzmann step
    """
    iso_grad = isotropic_gradient_symbolic(phi_field, stencil)
    tmp = (sum(map(lambda x: x * x, isotropic_gradient_symbolic(phi_field, stencil))) + 1.e-32) ** 0.5

    result = [x / tmp for x in iso_grad]
    return result


def pressure_force(phi_field, stencil, density_heavy, density_light):
    r"""
    Get a symbolic expression for the pressure force
    Args:
        phi_field: phase-field
        stencil: stencil of the lattice Boltzmann step
        density_heavy: density of the heavier fluid
        density_light: density of the lighter fluid
    """
    iso_grad = isotropic_gradient_symbolic(phi_field, stencil)
    result = list(map(lambda x: sp.Rational(-1, 3) * sp.symbols("rho") * (density_heavy - density_light) * x, iso_grad))
    return result


def viscous_force(lb_velocity_field, phi_field, mrt_method, tau, density_heavy, density_light):
    r"""
    Get a symbolic expression for the viscous force
    Args:
        lb_velocity_field: hydrodynamic distribution function
        phi_field: phase-field
        mrt_method: mrt lattice boltzmann method used for hydrodynamics
        tau: relaxation time of the hydrodynamic lattice boltzmann step
        density_heavy: density of the heavier fluid
        density_light: density of the lighter fluid
    """
    stencil = mrt_method.stencil
    dimensions = len(stencil[0])

    iso_grad = isotropic_gradient_symbolic(phi_field, stencil)

    moment_matrix = mrt_method.moment_matrix
    rel = mrt_method.relaxation_rates
    eq = mrt_method.moment_equilibrium_values
    eq = np.array(eq)

    g_vals = [lb_velocity_field.center(i) for i, _ in enumerate(stencil)]
    m0 = np.dot(moment_matrix, g_vals)

    m = m0 - eq
    m = m * rel
    non_equilibrium = np.dot(moment_matrix.inv(), m)

    stress_tensor = [0] * 6
    # Calculate Stress Tensor MRT
    for i, d in enumerate(stencil):
        stress_tensor[0] = sp.Add(stress_tensor[0], non_equilibrium[i] * (d[0] * d[0]))
        stress_tensor[1] = sp.Add(stress_tensor[1], non_equilibrium[i] * (d[1] * d[1]))

        if dimensions == 3:
            stress_tensor[2] = sp.Add(stress_tensor[2], non_equilibrium[i] * (d[2] * d[2]))
            stress_tensor[3] = sp.Add(stress_tensor[3], non_equilibrium[i] * (d[1] * d[2]))
            stress_tensor[4] = sp.Add(stress_tensor[4], non_equilibrium[i] * (d[0] * d[2]))

        stress_tensor[5] = sp.Add(stress_tensor[5], non_equilibrium[i] * (d[0] * d[1]))

    density_difference = density_heavy - density_light

    # Calculate Viscous Force MRT
    fmx = (0.5 - tau) * (stress_tensor[0] * iso_grad[0]
                         + stress_tensor[5] * iso_grad[1]
                         + stress_tensor[4] * iso_grad[2]) * density_difference

    fmy = (0.5 - tau) * (stress_tensor[5] * iso_grad[0]
                         + stress_tensor[1] * iso_grad[1]
                         + stress_tensor[3] * iso_grad[2]) * density_difference

    fmz = (0.5 - tau) * (stress_tensor[4] * iso_grad[0]
                         + stress_tensor[3] * iso_grad[1]
                         + stress_tensor[2] * iso_grad[2]) * density_difference

    return [fmx, fmy, fmz]


def surface_tension_force(phi_field, stencil, beta, kappa):
    r"""
    Get a symbolic expression for the surface tension force
    Args:
        phi_field: the phase-field on which the chemical potential is applied
        stencil: stencil of the lattice Boltzmann step
        beta: coefficient related to surface tension and interface thickness
        kappa: coefficient related to surface tension and interface thickness
    """
    chemical_potential = chemical_potential_symbolic(phi_field, stencil, beta, kappa)
    iso_grad = isotropic_gradient_symbolic(phi_field, stencil)
    return [chemical_potential * x for x in iso_grad]


def hydrodynamic_force(lb_velocity_field, phi_field, lb_method, tau,
                       density_heavy, density_light, kappa, beta, body_force):
    r"""
    Get a symbolic expression for the hydrodynamic force
    Args:
        lb_velocity_field: hydrodynamic distribution function
        phi_field: phase-field
        lb_method: Lattice boltzmann method used for hydrodynamics
        tau: relaxation time of the hydrodynamic lattice boltzmann step
        density_heavy: density of the heavier fluid
        density_light: density of the lighter fluid
        beta: coefficient related to surface tension and interface thickness
        kappa: coefficient related to surface tension and interface thickness
        body_force: force acting on the fluids. Usually the gravity
    """
    stencil = lb_method.stencil
    dimensions = len(stencil[0])
    fp = pressure_force(phi_field, stencil, density_heavy, density_light)
    fm = viscous_force(lb_velocity_field, phi_field, lb_method, tau, density_heavy, density_light)
    fs = surface_tension_force(phi_field, stencil, beta, kappa)

    result = []
    for i in range(dimensions):
        result.append(fs[i] + fp[i] + fm[i] + body_force[i])

    return result


def interface_tracking_force(phi_field, stencil, interface_thickness):
    r"""
    Get a symbolic expression for the hydrodynamic force
    Args:
        phi_field: phase-field
        stencil: stencil of the phase-field distribution lattice Boltzmann step
        interface_thickness: interface thickness
    """
    dimensions = len(stencil[0])
    normal_fd = normalized_isotropic_gradient_symbolic(phi_field, stencil)
    result = []
    for i in range(dimensions):
        result.append(((1.0 - 4.0 * (phi_field.center - 0.5) ** 2.0) / interface_thickness) * normal_fd[i])

    return result


def get_update_rules_velocity(src_field, u_in, lb_method, force, density):
    r"""
     Get assignments to update the velocity with a force shift
     Args:
         src_field: the source field of the hydrodynamic distribution function
         u_in: velocity field
         lb_method: mrt lattice boltzmann method used for hydrodynamics
         force: force acting on the hydrodynamic lb step
         density: the interpolated density of the simulation
     """
    stencil = lb_method.stencil
    dimensions = len(stencil[0])

    moment_matrix = lb_method.moment_matrix
    eq = lb_method.moment_equilibrium_values

    first_eqs = lb_method.first_order_equilibrium_moment_symbols
    indices = list()
    for i in range(dimensions):
        indices.append(eq.index(first_eqs[i]))

    src = [src_field.center(i) for i, _ in enumerate(stencil)]
    m0 = np.dot(moment_matrix, src)

    update_u = list()
    update_u.append(Assignment(sp.symbols("rho"), m0[0]))

    u_symp = sp.symbols("u_:{}".format(dimensions))
    zw = sp.symbols("zw_:{}".format(dimensions))
    for i in range(dimensions):
        update_u.append(Assignment(zw[i], u_in.center_vector[i]))

    subs_dict = dict(zip(u_symp, zw))
    for i in range(dimensions):
        update_u.append(Assignment(u_in.center_vector[i], m0[indices[i]] + force[i].subs(subs_dict) / density / 2))

    return update_u


def get_collision_assignments_hydro(collision_rule=None, density=1, optimization={}, **kwargs):
    r"""
     Get collision assignments for the hydrodynamic lattice Boltzmann step. Here the force gets applied in the moment
     space. Afterwards the transformation back to the pdf space happens.
     Args:
         collision_rule: arbitrary collision rule, e.g. created with create_lb_collision_rule
         density: the interpolated density of the simulation
         optimization: for details see createfunctions.py
     """
    params, opt_params = update_with_default_parameters(kwargs, optimization)

    lb_method = params['lb_method']

    stencil = lb_method.stencil
    dimensions = len(stencil[0])

    field_data_type = 'float64' if opt_params['double_precision'] else 'float32'
    q = len(stencil)

    u_in = params['velocity_input']
    force = params['force']

    if opt_params['symbolic_field'] is not None:
        src_field = opt_params['symbolic_field']
    elif opt_params['field_size']:
        field_size = [s + 2 for s in opt_params['field_size']] + [q]
        src_field = Field.create_fixed_size(params['field_name'], field_size, index_dimensions=1,
                                            layout=opt_params['field_layout'], dtype=field_data_type)
    else:
        src_field = Field.create_generic(params['field_name'], spatial_dimensions=collision_rule.method.dim,
                                         index_shape=(q,), layout=opt_params['field_layout'], dtype=field_data_type)

    if opt_params['symbolic_temporary_field'] is not None:
        dst_field = opt_params['symbolic_temporary_field']
    else:
        dst_field = src_field.new_field_with_different_name(params['temporary_field_name'])

    moment_matrix = lb_method.moment_matrix
    rel = lb_method.relaxation_rates
    eq = lb_method.moment_equilibrium_values

    first_eqs = lb_method.first_order_equilibrium_moment_symbols
    indices = list()
    for i in range(dimensions):
        indices.append(eq.index(first_eqs[i]))

    eq = np.array(eq)

    g_vals = [src_field.center(i) for i, _ in enumerate(stencil)]
    m0 = np.dot(moment_matrix, g_vals)

    mf = np.zeros(len(stencil), dtype=object)
    for i in range(dimensions):
        mf[indices[i]] = force[i] / density

    m = sp.symbols("m_:{}".format(len(stencil)))

    update_m = get_update_rules_velocity(src_field, u_in, lb_method, force, density)
    u_symp = sp.symbols("u_:{}".format(dimensions))

    for i in range(dimensions):
        update_m.append(Assignment(u_symp[i], u_in.center_vector[i]))

    for i in range(0, len(stencil)):
        update_m.append(Assignment(m[i], m0[i] - (m0[i] - eq[i] + mf[i] / 2) * rel[i] + mf[i]))

    update_g = list()
    var = np.dot(moment_matrix.inv(), m)
    if params['kernel_type'] == 'collide_stream_push':
        push_accessor = StreamPushTwoFieldsAccessor()
        post_collision_accesses = push_accessor.write(dst_field, stencil)
    else:
        collide_accessor = CollideOnlyInplaceAccessor()
        post_collision_accesses = collide_accessor.write(src_field, stencil)

    for i in range(0, len(stencil)):
        update_g.append(Assignment(post_collision_accesses[i], var[i]))

    hydro_lb_update_rule = AssignmentCollection(main_assignments=update_g,
                                                subexpressions=update_m)

    return hydro_lb_update_rule


def initializer_kernel_phase_field_lb(phi_field_distributions, phi_field, velocity, mrt_method, interface_thickness):
    r"""
    Returns an assignment list for initializing the phase-field distribution functions
    Args:
        phi_field_distributions: source field of phase-field distribution function
        phi_field: phase-field
        velocity: velocity field
        mrt_method: lattice Boltzmann method of the phase-field lattice Boltzmann step
        interface_thickness: interface thickness
    """
    stencil = mrt_method.stencil
    dimensions = len(stencil[0])
    weights = get_weights(stencil, c_s_sq=sp.Rational(1, 3))
    u_symp = sp.symbols("u_:{}".format(dimensions))

    normal_fd = normalized_isotropic_gradient_symbolic(phi_field, stencil)

    gamma = mrt_method.get_equilibrium_terms()
    gamma = gamma.subs({sp.symbols("rho"): 1})
    gamma_init = gamma.subs({x: y for x, y in zip(u_symp, velocity.center_vector)})
    # create the kernels for the initialization of the h field
    h_updates = list()

    def scalar_product(a, b):
        return sum(a_i * b_i for a_i, b_i in zip(a, b))

    f = []
    for i, d in enumerate(stencil):
        f.append(weights[i] * ((1.0 - 4.0 * (phi_field.center - 0.5) ** 2.0) / interface_thickness)
                 * scalar_product(d, normal_fd[0:dimensions]))

    for i, _ in enumerate(stencil):
        h_updates.append(Assignment(phi_field_distributions.center(i), phi_field.center * gamma_init[i] - 0.5 * f[i]))

    return h_updates


def initializer_kernel_hydro_lb(velocity_distributions, velocity, mrt_method):
    r"""
    Returns an assignment list for initializing the velocity distribution functions
    Args:
        velocity_distributions: source field of velocity distribution function
        velocity: velocity field
        mrt_method: lattice Boltzmann method of the hydrodynamic lattice Boltzmann step
    """
    stencil = mrt_method.stencil
    dimensions = len(stencil[0])
    weights = get_weights(stencil, c_s_sq=sp.Rational(1, 3))
    u_symp = sp.symbols("u_:{}".format(dimensions))

    gamma = mrt_method.get_equilibrium_terms()
    gamma = gamma.subs({sp.symbols("rho"): 1})
    gamma_init = gamma.subs({x: y for x, y in zip(u_symp, velocity.center_vector)})

    g_updates = list()
    for i, _ in enumerate(stencil):
        g_updates.append(Assignment(velocity_distributions.center(i), gamma_init[i] - weights[i]))

    return g_updates
