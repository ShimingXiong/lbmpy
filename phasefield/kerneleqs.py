import sympy as sp
from pystencils.finitedifferences import Discretization2ndOrder
from lbmpy.phasefield.analytical import chemicalPotentialsFromFreeEnergy, substituteLaplacianBySum, \
    forceFromPhiAndMu, symmetricTensorLinearization, pressureTensorFromFreeEnergy, forceFromPressureTensor


# ---------------------------------- Kernels to compute force ----------------------------------------------------------


def muKernel(freeEnergy, orderParameters, phiField, muField, dx=1):
    """Reads from order parameter (phi) field and updates chemical potentials"""
    assert phiField.spatialDimensions == muField.spatialDimensions
    dim = phiField.spatialDimensions
    chemicalPotential = chemicalPotentialsFromFreeEnergy(freeEnergy, orderParameters)
    chemicalPotential = substituteLaplacianBySum(chemicalPotential, dim)
    chemicalPotential = chemicalPotential.subs({op: phiField(i) for i, op in enumerate(orderParameters)})
    discretize = Discretization2ndOrder(dx=dx)
    return [sp.Eq(muField(i), discretize(mu_i)) for i, mu_i in enumerate(chemicalPotential)]


def forceKernelUsingMu(forceField, phiField, muField, dx=1):
    """Computes forces using precomputed chemical potential - needs muKernel first"""
    assert muField.indexDimensions == 1
    force = forceFromPhiAndMu(phiField.vecCenter, mu=muField.vecCenter, dim=muField.spatialDimensions)
    discretize = Discretization2ndOrder(dx=dx)
    return [sp.Eq(forceField(i),
                  discretize(f_i)).expand() for i, f_i in enumerate(force)]


def pressureTensorKernel(freeEnergy, orderParameters, phiField, pressureTensorField, dx=1):
    dim = phiField.spatialDimensions
    p = pressureTensorFromFreeEnergy(freeEnergy, orderParameters, dim)
    p = p.subs({op: phiField(i) for i, op in enumerate(orderParameters)})
    indexMap = symmetricTensorLinearization(dim)
    discretize = Discretization2ndOrder(dx=dx)
    eqs = []
    for index, linIndex in indexMap.items():
        eq = sp.Eq(pressureTensorField(linIndex),
                   discretize(p[index]).expand())
        eqs.append(eq)
    return eqs


def forceKernelUsingPressureTensor(forceField, pressureTensorField, extraForce=None, dx=1):
    dim = forceField.spatialDimensions
    indexMap = symmetricTensorLinearization(dim)

    p = sp.Matrix(dim, dim, lambda i, j: pressureTensorField(indexMap[i, j] if i < j else indexMap[j, i]))
    f = forceFromPressureTensor(p)
    if extraForce:
        f += extraForce
    discretize = Discretization2ndOrder(dx=dx)
    return [sp.Eq(forceField(i), discretize(f_i).expand())
            for i, f_i in enumerate(f)]


# ---------------------------------- Cahn Hilliard with finite differences ---------------------------------------------


def cahnHilliardFdEq(phaseIdx, phi, mu, velocity, mobility, dx, dt):
    from pystencils.finitedifferences import transient, advection, diffusion
    cahnHilliard = transient(phi, phaseIdx) + advection(phi, velocity, phaseIdx) - diffusion(mu, mobility, phaseIdx)
    return Discretization2ndOrder(dx, dt)(cahnHilliard)


class CahnHilliardFDStep:
    def __init__(self, dataHandling, phiFieldName, muFieldName, velocityFieldName, name='ch_fd', target='cpu',
                 dx=1, dt=1, mobilities=1, equationModifier=lambda eqs: eqs):
        from pystencils import createKernel
        self.dataHandling = dataHandling

        muField = self.dataHandling.fields[muFieldName]
        velField = self.dataHandling.fields[velocityFieldName]
        self.phiField = self.dataHandling.fields[phiFieldName]
        self.tmpField = self.dataHandling.addArrayLike(name + '_tmp', phiFieldName, latexName='tmp')

        numPhases = self.dataHandling.fSize(phiFieldName)
        if not hasattr(mobilities, '__len__'):
            mobilities = [mobilities] * numPhases

        updateEqs = []
        for i in range(numPhases):
            rhs = cahnHilliardFdEq(i, self.phiField, muField, velField, mobilities[i], dx, dt)
            updateEqs.append(sp.Eq(self.tmpField(i), rhs))
        self.updateEqs = updateEqs
        self.updateEqs = equationModifier(updateEqs)
        self.kernel = createKernel(self.updateEqs, target=target).compile()
        self.sync = self.dataHandling.synchronizationFunction([phiFieldName, velocityFieldName, muFieldName],
                                                              target=target)

    def timeStep(self, **kwargs):
        self.sync()
        self.dataHandling.runKernel(self.kernel, **kwargs)
        self.dataHandling.swap(self.phiField.name, self.tmpField.name)

    def setPdfFieldsFromMacroscopicValues(self):
        pass

    def preRun(self):
        pass

    def postRun(self):
        pass
