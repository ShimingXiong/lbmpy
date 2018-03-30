import numpy as np
import sympy as sp

from pystencils import Field, Assignment
from pystencils.assignment_collection.assignment_collection import AssignmentCollection
from pystencils.field import createNumpyArrayWithLayout, layoutStringToTuple
from pystencils.sympyextensions import fastSubs
from lbmpy.methods.abstractlbmethod import LbmCollisionRule
from lbmpy.fieldaccess import StreamPullTwoFieldsAccessor, PeriodicTwoFieldsAccessor, CollideOnlyInplaceAccessor


# -------------------------------------------- LBM Kernel Creation -----------------------------------------------------


def createLBMKernel(collisionRule, inputField, outputField, accessor):
    """
    Replaces the pre- and post collision symbols in the collision rule by field accesses.

    :param collisionRule:  instance of LbmCollisionRule, defining the collision step
    :param inputField: field used for reading pdf values
    :param outputField: field used for writing pdf values (may be the same as input field for certain accessors)
    :param accessor: instance of PdfFieldAccessor, defining where to read and write values
                     to create e.g. a fused stream-collide kernel
    :return: LbmCollisionRule where pre- and post collision symbols have been replaced
    """
    method = collisionRule.method
    preCollisionSymbols = method.preCollisionPdfSymbols
    postCollisionSymbols = method.postCollisionPdfSymbols
    substitutions = {}

    inputAccesses = accessor.read(inputField, method.stencil)
    outputAccesses = accessor.write(outputField, method.stencil)

    for (idx, offset), inputAccess, outputAccess in zip(enumerate(method.stencil), inputAccesses, outputAccesses):
        substitutions[preCollisionSymbols[idx]] = inputAccess
        substitutions[postCollisionSymbols[idx]] = outputAccess

    result = collisionRule.copyWithSubstitutionsApplied(substitutions)

    if 'splitGroups' in result.simplificationHints:
        newSplitGroups = []
        for splitGroup in result.simplificationHints['splitGroups']:
            newSplitGroups.append([fastSubs(e, substitutions) for e in splitGroup])
        result.simplificationHints['splitGroups'] = newSplitGroups

    return result


def createStreamPullCollideKernel(collisionRule, numpyField=None, srcFieldName="src", dstFieldName="dst",
                                  genericLayout='numpy', genericFieldType=np.float64,
                                  builtinPeriodicity=(False, False, False)):
    """
    Implements a stream-pull scheme, where values are read from source and written to destination field
    :param collisionRule: a collision rule created by lbm method
    :param numpyField: optional numpy field for PDFs. Used to create a kernel of fixed loop bounds and strides
                       if None, a generic kernel is created
    :param srcFieldName: name of the pdf source field
    :param dstFieldName: name of the pdf destination field
    :param genericLayout: if no numpyField is given to determine the layout, a variable sized field with the given
                          genericLayout is used
    :param genericFieldType: if no numpyField is given, this data type is used for the fields
    :param builtinPeriodicity: periodicity that should be built into the kernel
    :return: lbm update rule, where generic pdf references are replaced by field accesses
    """
    dim = collisionRule.method.dim
    if numpyField is not None:
        assert len(numpyField.shape) == dim + 1, "Field dimension mismatch: dimension is %s, should be %d" % \
                                                 (len(numpyField.shape), dim + 1)

    if numpyField is None:
        src = Field.createGeneric(srcFieldName, dim, indexDimensions=1, layout=genericLayout, dtype=genericFieldType)
        dst = Field.createGeneric(dstFieldName, dim, indexDimensions=1, layout=genericLayout, dtype=genericFieldType)
    else:
        src = Field.createFromNumpyArray(srcFieldName, numpyField, indexDimensions=1)
        dst = Field.createFromNumpyArray(dstFieldName, numpyField, indexDimensions=1)

    accessor = StreamPullTwoFieldsAccessor

    if any(builtinPeriodicity):
        accessor = PeriodicTwoFieldsAccessor(builtinPeriodicity, ghostLayers=1)
    return createLBMKernel(collisionRule, src, dst, accessor)


def createCollideOnlyKernel(collisionRule, numpyField=None, fieldName="src",
                            genericLayout='numpy', genericFieldType=np.float64):
    """
    Implements a collision only (no neighbor access) LBM kernel.
    For parameters see function ``createStreamPullCollideKernel``
    """
    dim = collisionRule.method.dim
    if numpyField is not None:
        assert len(numpyField.shape) == dim + 1, "Field dimension mismatch: dimension is %s, should be %d" % \
                                                 (len(numpyField.shape), dim + 1)

    if numpyField is None:
        field = Field.createGeneric(fieldName, dim, indexDimensions=1, layout=genericLayout, dtype=genericFieldType)
    else:
        field = Field.createFromNumpyArray(fieldName, numpyField, indexDimensions=1)

    return createLBMKernel(collisionRule, field, field, CollideOnlyInplaceAccessor)


def createStreamPullOnlyKernel(stencil, numpyField=None, srcFieldName="src", dstFieldName="dst",
                               genericLayout='numpy', genericFieldType=np.float64):
    """
    Creates a stream-pull kernel, without collision
    For parameters see function ``createStreamPullCollideKernel``
    """

    dim = len(stencil[0])
    if numpyField is None:
        src = Field.createGeneric(srcFieldName, dim, indexDimensions=1, layout=genericLayout, dtype=genericFieldType)
        dst = Field.createGeneric(dstFieldName, dim, indexDimensions=1, layout=genericLayout, dtype=genericFieldType)
    else:
        src = Field.createFromNumpyArray(srcFieldName, numpyField, indexDimensions=1)
        dst = Field.createFromNumpyArray(dstFieldName, numpyField, indexDimensions=1)

    accessor = StreamPullTwoFieldsAccessor()
    eqs = [Assignment(a, b) for a, b in zip(accessor.write(dst, stencil), accessor.read(src, stencil))
           if Assignment(a, b) != True]
    return AssignmentCollection(eqs, [])


def createStreamPullWithOutputKernel(lbMethod, srcField, dstField, output):
    stencil = lbMethod.stencil
    cqc = lbMethod.conservedQuantityComputation
    streamed = sp.symbols("streamed_:%d" % (len(stencil),))
    accessor = StreamPullTwoFieldsAccessor()
    streamEqs = [Assignment(a, b) for a, b in zip(streamed, accessor.read(srcField, stencil))
                 if Assignment(a, b) != True]
    outputEqCollection = cqc.outputEquationsFromPdfs(streamed, output)
    writeEqs = [Assignment(a, b) for a, b in zip(accessor.write(dstField, stencil), streamed)]

    subExprs = streamEqs + outputEqCollection.subexpressions
    mainEqs = outputEqCollection.mainAssignments + writeEqs
    return LbmCollisionRule(lbMethod, mainEqs, subExprs, simplificationHints=outputEqCollection.simplificationHints)

# ---------------------------------- Pdf array creation for various layouts --------------------------------------------


def createPdfArray(size, numDirections, ghostLayers=1, layout='fzyx'):
    """
    Creates an empty numpy array for a pdf field with the specified memory layout.

    Examples:
        >>> createPdfArray((3, 4, 5), 9, layout='zyxf', ghostLayers=0).shape
        (3, 4, 5, 9)
        >>> createPdfArray((3, 4, 5), 9, layout='zyxf', ghostLayers=0).strides
        (72, 216, 864, 8)
        >>> createPdfArray((3, 4), 9, layout='zyxf', ghostLayers=1).shape
        (5, 6, 9)
        >>> createPdfArray((3, 4), 9, layout='zyxf', ghostLayers=1).strides
        (72, 360, 8)
    """
    sizeWithGl = [s + 2 * ghostLayers for s in size]
    dim = len(size)
    if isinstance(layout, str):
        layout = layoutStringToTuple(layout, dim+1)
    return createNumpyArrayWithLayout(sizeWithGl + [numDirections], layout)


# ------------------------------------------- Add output fields to kernel ----------------------------------------------


def addOutputFieldForConservedQuantities(collisionRule, conservedQuantitiesToOutputFieldDict):
    method = collisionRule.method
    cqc = method.conservedQuantityComputation.outputEquationsFromPdfs(method.preCollisionPdfSymbols,
                                                                      conservedQuantitiesToOutputFieldDict)
    return collisionRule.merge(cqc)


def writeQuantitiesToField(collisionRule, symbols, outputField):
    if not hasattr(symbols, "__len__"):
        symbols = [symbols]
    eqs = [Assignment(outputField(i), s) for i, s in enumerate(symbols)]
    return collisionRule.copy(collisionRule.mainAssignments + eqs)
