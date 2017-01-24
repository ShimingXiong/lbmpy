import sympy as sp

from lbmpy.simplificationfactory import createSimplificationStrategy
from pystencils.sympyextensions import getSymmetricPart
from lbmpy.boundaries.boundaryhandling import offsetFromDir, weightOfDirection, invDir


def noSlip(pdfField, direction, lbmMethod):
    """No-Slip, simple bounce back boundary condition, enforcing zero velocity at obstacle"""
    neighbor = offsetFromDir(direction, lbmMethod.dim)
    inverseDir = invDir(direction)
    return [sp.Eq(pdfField[neighbor](inverseDir), pdfField(direction))]


def ubb(pdfField, direction, lbmMethod, velocity):
    """Velocity bounce back boundary condition, enforcing specified velocity at obstacle"""

    assert len(velocity) == lbmMethod.dim, \
        "Dimension of velocity (%d) does not match dimension of LB method (%d)" % (len(velocity, lbmMethod.dim))
    neighbor = offsetFromDir(direction, lbmMethod.dim)
    inverseDir = invDir(direction)

    velTerm = 6 * sum([d_i * v_i for d_i, v_i in zip(neighbor, velocity)]) * weightOfDirection(direction)
    return [sp.Eq(pdfField[neighbor](inverseDir),
                  pdfField(direction) - velTerm)]


def fixedDensity(pdfField, direction, lbmMethod, density):
    """Boundary condition that fixes the density/pressure at the obstacle"""

    def removeAsymmetricPartOfMainEquations(eqColl, dofs):
        newMainEquations = [sp.Eq(e.lhs, getSymmetricPart(e.rhs, dofs)) for e in eqColl.mainEquations]
        return eqColl.copy(newMainEquations)

    neighbor = offsetFromDir(direction, lbmMethod.dim)
    inverseDir = invDir(direction)

    symmetricEq = removeAsymmetricPartOfMainEquations(lbmMethod.getEquilibrium())
    simplification = createSimplificationStrategy(lbmMethod)
    symmetricEq = simplification(symmetricEq)

    densitySymbol = lbmMethod.conservedQuantityComputation.definedSymbols()['density']

    conditions = [(eq_i.rhs, sp.Equality(direction, i))
                  for i, eq_i in enumerate(symmetricEq.mainEquations)] + [(0, True)]
    eq_component = sp.Piecewise(*conditions)

    subExprs = [sp.Eq(eq.lhs, density if eq.lhs == densitySymbol else eq.rhs) for eq in symmetricEq.subexpressions]
    return subExprs + [sp.Eq(pdfField[neighbor](inverseDir), 2 * eq_component - pdfField(direction))]
