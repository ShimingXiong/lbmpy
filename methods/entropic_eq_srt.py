import sympy as sp
from pystencils import Assignment
from lbmpy.maxwellian_equilibrium import get_weights
from lbmpy.methods.abstractlbmethod import AbstractLbMethod, LbmCollisionRule
from lbmpy.methods.conservedquantitycomputation import DensityVelocityComputation


class EntropicEquilibriumSRT(AbstractLbMethod):
    def __init__(self, stencil, relaxation_rate, force_model, conserved_quantity_calculation):
        super(EntropicEquilibriumSRT, self).__init__(stencil)

        self._cqc = conserved_quantity_calculation
        self._weights = get_weights(stencil, c_s_sq=sp.Rational(1, 3))
        self._relaxationRate = relaxation_rate
        self._forceModel = force_model
        self.shearRelaxationRate = relaxation_rate

    @property
    def conserved_quantity_computation(self):
        return self._cqc

    @property
    def weights(self):
        return self._weights

    @property
    def zeroth_order_equilibrium_moment_symbol(self, ):
        return self._cqc.zeroth_order_moment_symbol

    @property
    def first_order_equilibrium_moment_symbols(self, ):
        return self._cqc.first_order_moment_symbols

    def get_equilibrium(self, conserved_quantity_equations=None, include_force_terms=False):
        return self._get_collision_rule_with_relaxation_rate(1,
                                                             conserved_quantity_equations=conserved_quantity_equations,
                                                             include_force_terms=include_force_terms)

    def _get_collision_rule_with_relaxation_rate(self, relaxation_rate, include_force_terms=True,
                                                 conserved_quantity_equations=None):
        f = sp.Matrix(self.pre_collision_pdf_symbols)
        rho = self._cqc.zeroth_order_moment_symbol
        u = self._cqc.first_order_moment_symbols

        if conserved_quantity_equations is None:
            conserved_quantity_equations = self._cqc.equilibrium_input_equations_from_pdfs(f)
        all_subexpressions = conserved_quantity_equations.allEquations

        eq = []
        for w_i, direction in zip(self.weights, self.stencil):
            f_i = rho * w_i
            for u_a, e_ia in zip(u, direction):
                B = sp.sqrt(1 + 3 * u_a ** 2)
                f_i *= (2 - B) * ((2 * u_a + B) / (1 - u_a)) ** e_ia
            eq.append(f_i)

        collision_eqs = [Assignment(lhs, (1 - relaxation_rate) * f_i + relaxation_rate * eq_i)
                         for lhs, f_i, eq_i in zip(self.post_collision_pdf_symbols, self.pre_collision_pdf_symbols, eq)]

        if (self._forceModel is not None) and include_force_terms:
            force_model_terms = self._forceModel(self)
            force_term_symbols = sp.symbols("forceTerm_:%d" % (len(force_model_terms, )))
            force_subexpressions = [Assignment(sym, forceModelTerm)
                                   for sym, forceModelTerm in zip(force_term_symbols, force_model_terms)]
            all_subexpressions += force_subexpressions
            collision_eqs = [Assignment(eq.lhs, eq.rhs + forceTermSymbol)
                             for eq, forceTermSymbol in zip(collision_eqs, force_term_symbols)]

        return LbmCollisionRule(self, collision_eqs, all_subexpressions)

    def get_collision_rule(self):
        return self._get_collision_rule_with_relaxation_rate(self._relaxationRate)


def create_srt_entropic(stencil, relaxation_rate, force_model, compressible):
    if not compressible:
        raise NotImplementedError("entropic-srt only implemented for compressible models")
    density_velocity_computation = DensityVelocityComputation(stencil, compressible, force_model)
    return EntropicEquilibriumSRT(stencil, relaxation_rate, force_model, density_velocity_computation)
