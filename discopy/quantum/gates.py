# -*- coding: utf-8 -*-

""" Gates in a :class:`discopy.quantum.circuit.Circuit`. """

from collections.abc import Callable
import numpy

from discopy.cat import AxiomError, rsubs
from discopy.tensor import array2string, Dim, Tensor
from discopy.quantum.circuit import (
    Digit, Ty, bit, qubit, Box, Swap, Sum, Id,
    AntiConjugate, RealConjugate, Anti2QubitConjugate)


def format_number(data):
    """ Tries to format a number. """
    try:
        return '{:.3g}'.format(data)
    except TypeError:
        return data


class QuantumGate(Box):
    """ Quantum gates, i.e. unitaries on n qubits. """
    def __init__(
            self, name, n_qubits, array=None, data=None,
            _dagger=False, _conjugate=False):
        dom = qubit ** n_qubits
        if array is not None:
            self._array = Tensor.np.array(array).reshape(
                2 * n_qubits * (2, ) or (1, ))
        super().__init__(
            name, dom, dom, is_mixed=False, data=data,
            _dagger=_dagger, _conjugate=_conjugate)

    @property
    def array(self):
        """ The array of a quantum gate. """
        return self._array

    def __repr__(self):
        if self in GATES:
            return self.name
        elif self.conjugate() in GATES:
            return self.name + '.conjugate()'
        elif self.dagger() in GATES:
            return self.name + '.dagger()'
        elif self.dagger().conjugate() in GATES:
            return self.name + '.conjugate().dagger()'
        more_info = ", _dagger=True" if self._dagger else ""
        more_info += ", _conjugate=True" if self._conjugate else ""

        return ("QuantumGate({}, n_qubits={}, array={}{})").format(
            repr(self.name), len(self.dom),
            array2string(self.array.flatten()), more_info)

    def dagger(self):
        dagger = None if self._dagger is None else not self._dagger
        return QuantumGate(
            self.name, len(self.dom), self.array,
            _conjugate=self._conjugate, _dagger=dagger)

    def conjugate(self):
        conjugate = None if self._conjugate is None else not self._conjugate
        return QuantumGate(
            self.name, len(self.dom), self.array,
            _dagger=self._dagger, _conjugate=conjugate)

    l = r = property(conjugate)


class ClassicalGate(Box):
    """
    Classical gates, i.e. from digits to digits.

    >>> from sympy import symbols
    >>> array = symbols("a b c d")
    >>> f = ClassicalGate('f', 1, 1, array)
    >>> f
    ClassicalGate('f', bit, bit, data=[a, b, c, d])
    >>> f.lambdify(*array)(1, 2, 3, 4)
    ClassicalGate('f', bit, bit, data=[1, 2, 3, 4])
    """
    def __init__(self, name, dom, cod, data=None, _dagger=False):
        if isinstance(dom, int):
            dom = bit ** dom
        if isinstance(cod, int):
            cod = bit ** cod
        if data is not None:
            data = Tensor.np.array(data).reshape(
                (len(dom) + len(cod)) * (2, ) or (1, ))
        super().__init__(
            name, dom, cod, is_mixed=False, data=data, _dagger=_dagger)

    @property
    def array(self):
        """ The array of a classical gate. """
        return self.data

    def __eq__(self, other):
        if not isinstance(other, ClassicalGate):
            return super().__eq__(other)
        return (self.name, self.dom, self.cod)\
            == (other.name, other.dom, other.cod)\
            and Tensor.np.all(self.array == other.array)

    def __repr__(self):
        if self.is_dagger:
            return repr(self.dagger()) + ".dagger()"
        data = array2string(self.array.flatten())
        return "ClassicalGate({}, {}, {}, data={})"\
            .format(repr(self.name), self.dom, self.cod, data)

    def dagger(self):
        _dagger = None if self._dagger is None else not self._dagger
        return ClassicalGate(
            self.name, self.cod, self.dom, self.array, _dagger)

    def subs(self, *args):
        data = rsubs(list(self.data.flatten()), *args)
        return ClassicalGate(self.name, self.dom, self.cod, data)

    def lambdify(self, *symbols, **kwargs):
        from sympy import lambdify
        data = lambdify(symbols, self.data, dict(kwargs, modules=Tensor.np))
        return lambda *xs: ClassicalGate(
            self.name, self.dom, self.cod, data(*xs))

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        name = "{}.grad({})".format(self.name, var)
        data = self.eval().grad(var, **params).array
        return ClassicalGate(name, self.dom, self.cod, data)


class Copy(RealConjugate, ClassicalGate):
    """ Takes a bit, returns two copies of it. """
    def __init__(self):
        super().__init__("Copy", 1, 2, [1, 0, 0, 0, 0, 0, 0, 1])
        self.draw_as_spider, self.color = True, "black"
        self.drawing_name = ""

    def dagger(self):
        return Match()


class Match(RealConjugate, ClassicalGate):
    """ Takes two bits in, returns them if they are equal. """
    def __init__(self):
        super().__init__("Match", 2, 1, [1, 0, 0, 0, 0, 0, 0, 1])
        self.draw_as_spider, self.color = True, "black"
        self.drawing_name = ""

    def dagger(self):
        return Copy()


class Digits(ClassicalGate):
    """
    Classical state for a given string of digits of a given dimension.

    Examples
    --------
    >>> assert Bits(1, 0) == Digits(1, 0, dim=2)
    >>> assert Digits(2, dim=4).eval()\\
    ...     == Tensor(dom=Dim(1), cod=Dim(4), array=[0, 0, 1, 0])
    """
    def __init__(self, *digits, dim=None, _dagger=False):
        if not isinstance(dim, int):
            raise TypeError(int, dim)
        self._digits, self._dim = digits, dim
        name = "Digits({}, dim={})".format(', '.join(map(str, digits)), dim)\
            if dim != 2 else "Bits({})".format(', '.join(map(str, digits)))
        dom, cod = Ty(), Ty(Digit(dim)) ** len(digits)
        dom, cod = (cod, dom) if _dagger else (dom, cod)
        super().__init__(name, dom, cod, _dagger=_dagger)

    def __repr__(self):
        return self.name + (".dagger()" if self._dagger else "")

    @property
    def dim(self):
        """
        The dimension of the information units.

        >>> assert Bits(1, 0).dim == 2
        """
        return self._dim

    @property
    def digits(self):
        """ The digits of a classical state. """
        return list(self._digits)

    @property
    def array(self):
        array = numpy.zeros(len(self._digits) * (self._dim, ) or (1, ))
        array[self._digits] = 1
        return array

    def dagger(self):
        return Digits(*self.digits, dim=self.dim, _dagger=not self._dagger)


class Bits(Digits):
    """
    Implements bit preparation for a given bitstring.

    >>> assert Bits(1, 0).cod == bit ** 2
    >>> assert Bits(1, 0).eval()\\
    ...     == Tensor(dom=Dim(1), cod=Dim(2, 2), array=[0, 0, 1, 0])
    """
    def __init__(self, *bitstring, _dagger=False):
        super().__init__(*bitstring, dim=2, _dagger=_dagger)

    @property
    def bitstring(self):
        """ The bitstring of a classical state. """
        return list(self._digits)

    def dagger(self):
        return Bits(*self.bitstring, _dagger=not self._dagger)


class Ket(RealConjugate, Box):
    """
    Implements qubit preparation for a given bitstring.

    >>> assert Ket(1, 0).cod == qubit ** 2
    >>> assert Ket(1, 0).eval()\\
    ...     == Tensor(dom=Dim(1), cod=Dim(2, 2), array=[0, 0, 1, 0])
    """
    def __init__(self, *bitstring):
        if not all([bit in [0, 1] for bit in bitstring]):
            raise Exception('Bitstring can only contain integers 0 or 1.')

        dom, cod = qubit ** 0, qubit ** len(bitstring)
        name = "Ket({})".format(', '.join(map(str, bitstring)))
        super().__init__(name, dom, cod, is_mixed=False)
        self._digits, self._dim, self.draw_as_brakets = bitstring, 2, True

    @property
    def bitstring(self):
        """ The bitstring of a Ket. """
        return list(self._digits)

    def dagger(self):
        return Bra(*self.bitstring)

    array = Bits.array


class Bra(RealConjugate, Box):
    """
    Implements qubit post-selection for a given bitstring.

    >>> assert Bra(1, 0).dom == qubit ** 2
    >>> assert Bra(1, 0).eval()\\
    ...     == Tensor(dom=Dim(2, 2), cod=Dim(1), array=[0, 0, 1, 0])
    """
    def __init__(self, *bitstring):
        if not all([bit in [0, 1] for bit in bitstring]):
            raise Exception('Bitstring can only contain integers 0 or 1.')

        name = "Bra({})".format(', '.join(map(str, bitstring)))
        dom, cod = qubit ** len(bitstring), qubit ** 0
        super().__init__(name, dom, cod, is_mixed=False)
        self._digits, self._dim, self.draw_as_brakets = bitstring, 2, True

    @property
    def bitstring(self):
        """ The bitstring of a Bra. """
        return list(self._digits)

    def dagger(self):
        return Ket(*self.bitstring)

    array = Bits.array


class Controlled(QuantumGate):
    """
    Abstract class for controled quantum gates.

    Parameters
    ----------
    controlled : QuantumGate
        Gate to control, e.g. :code:`CX = Controlled(X)`.
    distance : int, optional
        Number of qubits from the control to the target, default is :code:`0`.
        If negative, the control is on the right of the target.
    """
    def __init__(self, controlled, distance=0):
        if not isinstance(controlled, QuantumGate):
            raise TypeError(QuantumGate, controlled)
        self.controlled, self.distance = controlled, distance
        self.draw_as_controlled = True
        array = numpy.zeros((4, 4), dtype=complex)
        array[:2, :2] = numpy.eye(2)
        array[2:, 2:] = controlled.array
        if distance != 0:
            raise NotImplementedError
        name = "C" + controlled.name
        n_qubits = len(controlled.dom) + (
            distance + 1 if distance >= 0 else -distance)
        super().__init__(name, n_qubits, array)

    def dagger(self):
        return Controlled(self.controlled.dagger(), distance=self.distance)


class Parametrized(Box):
    """
    Abstract class for parametrized boxes in a quantum circuit.

    Parameters
    ----------
    name : str
        Name of the parametrized class, e.g. :code:`"CRz"`.
    dom, cod : discopy.quantum.circuit.Ty
        Domain and codomain.
    data : any
        Data of the box, potentially with free symbols.
    datatype : type
        Type to cast whenever there are no free symbols.

    Example
    -------
    >>> from sympy.abc import phi
    >>> from sympy import pi, exp, I
    >>> assert Rz(phi)\\
    ...     == Parametrized('Rz', qubit, qubit, data=phi, is_mixed=False)
    >>> assert Rz(phi).array[0,0] == exp(-1.0 * I * pi * phi)
    >>> c = Rz(phi) >> Rz(-phi)
    >>> assert list(c.eval().array.flatten()) == [1, 0, 0, 1]
    >>> assert c.lambdify(phi)(.25) == Rz(.25) >> Rz(-.25)
    """
    def __init__(self, name, dom, cod, data=None, **params):
        self.drawing_name = '{}({})'.format(name, data)
        Box.__init__(
            self, name, dom, cod, data=data,
            is_mixed=params.get('is_mixed', True),
            _dagger=params.get('_dagger', False))

    @property
    def modules(self):
        if self.free_symbols:
            import sympy
            return sympy
        else:
            return Tensor.np

    def subs(self, *args):
        data = rsubs(self.data, *args)
        return type(self)(data)

    def lambdify(self, *symbols, **kwargs):
        from sympy import lambdify
        data = lambdify(symbols, self.data, dict(kwargs, modules=Tensor.np))
        return lambda *xs: type(self)(data(*xs))

    @property
    def name(self):
        return '{}({})'.format(self._name, format_number(self.data))

    def __repr__(self):
        return self.name


class Rotation(Parametrized, QuantumGate):
    """ Abstract class for rotation gates. """
    def __init__(self, phase, name=None, n_qubits=1, _conjugate=False):
        QuantumGate.__init__(self, name, n_qubits, _conjugate=_conjugate)
        Parametrized.__init__(
            self, name, self.dom, self.cod,
            datatype=float, is_mixed=False, data=phase)

    @property
    def phase(self):
        """ The phase of a rotation gate. """
        return self.data

    def dagger(self):
        return type(self)(-self.phase)

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        gradient = self.phase.diff(var)
        gradient = complex(gradient) if not gradient.free_symbols else gradient

        if params.get('mixed', True):
            if len(self.dom) != 1:
                raise NotImplementedError
            s = scalar(Tensor.np.pi * gradient, is_mixed=True)
            t1 = type(self)(self.phase + .25)
            t2 = type(self)(self.phase - .25)
            return s @ (t1 + scalar(-1, is_mixed=True) @ t2)

        return scalar(Tensor.np.pi * gradient) @ type(self)(self.phase + .5)


class Rx(AntiConjugate, Rotation):
    """ X rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="Rx")

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        sin, cos = self.modules.sin(half_theta), self.modules.cos(half_theta)
        return Tensor.np.array([[cos, -1j * sin], [-1j * sin, cos]])


class Ry(RealConjugate, Rotation):
    """ Y rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="Ry", _conjugate=None)

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        sin, cos = self.modules.sin(half_theta), self.modules.cos(half_theta)
        return Tensor.np.array([[cos, -1 * sin], [sin, cos]])


class Rz(AntiConjugate, Rotation):
    """ Z rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="Rz")

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        return Tensor.np.array(
            [[self.modules.exp(-1j * half_theta), 0],
             [0, self.modules.exp(1j * half_theta)]])


def _outer_prod_diag(*bitstring):
    return Bra(*bitstring) >> Ket(*bitstring)


class CU1(Anti2QubitConjugate, Rotation):
    """ Controlled Z rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="CU1", n_qubits=2)

    @property
    def array(self):
        theta = 2 * self.modules.pi * self.phase
        return Tensor.np.array(
            [1, 0, 0, 0,
             0, 1, 0, 0,
             0, 0, 1, 0,
             0, 0, 0, self.modules.exp(1j * theta)]).reshape(2, 2, 2, 2)

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        if params.get('mixed', True):
            return super().grad(var, **params)
        gradient = self.phase.diff(var)
        gradient = complex(gradient) if not gradient.free_symbols else gradient
        _i_2_pi = 1j * 2 * self.modules.pi
        s = scalar(_i_2_pi * gradient * self.modules.exp(_i_2_pi * self.phase))
        return _outer_prod_diag(1, 1) @ s


class CRz(Anti2QubitConjugate, Rotation):
    """ Controlled Z rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="CRz", n_qubits=2)

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        exp_m = self.modules.exp(-1j * half_theta)
        exp_p = self.modules.exp(1j * half_theta)
        return Tensor.np.array(
            [1, 0, 0, 0,
             0, 1, 0, 0,
             0, 0, exp_m, 0,
             0, 0, 0, exp_p]).reshape(2, 2, 2, 2)

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        if params.get('mixed', True):
            return super().grad(var, **params)
        gradient = self.phase.diff(var)
        gradient = complex(gradient) if not gradient.free_symbols else gradient
        _i_half_pi = .5j * self.modules.pi
        op1 = Z @ Z @ scalar(_i_half_pi * gradient)
        op2 = Id(qubit) @ Z @ scalar(-_i_half_pi * gradient)
        return self >> (op1 + op2)


class CRx(Anti2QubitConjugate, Rotation):
    """ Controlled Z rotations. """
    def __init__(self, phase):
        super().__init__(phase, name="CRx", n_qubits=2)

    @property
    def array(self):
        half_theta = self.modules.pi * self.phase
        cos, sin = self.modules.cos(half_theta), self.modules.sin(half_theta)
        return Tensor.np.array(
            [1, 0, 0, 0,
             0, 1, 0, 0,
             0, 0, cos, -1j * sin,
             0, 0, -1j * sin, cos]).reshape(2, 2, 2, 2)

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        if params.get('mixed', True):
            return super().grad(var, **params)
        gradient = self.phase.diff(var)
        gradient = complex(gradient) if not gradient.free_symbols else gradient
        _i_half_pi = .5j * self.modules.pi
        op1 = Z @ X @ scalar(_i_half_pi * gradient)
        op2 = Id(qubit) @ X @ scalar(-_i_half_pi * gradient)
        return self >> (op1 + op2)


class Scalar(Parametrized):
    """ Scalar, i.e. quantum gate with empty domain and codomain. """
    def __init__(self, data, datatype=complex, name=None, is_mixed=False):
        self.drawing_name = format_number(data)
        name = "scalar" if name is None else name
        dom, cod = qubit ** 0, qubit ** 0
        _dagger = None if data.conjugate() == data else False
        super().__init__(
            name, dom, cod,
            datatype=datatype, is_mixed=is_mixed, data=data, _dagger=_dagger)

    def __repr__(self):
        return super().__repr__()[:-1] + (
            ', is_mixed=True)' if self.is_mixed else ')')

    @property
    def array(self):
        return [self.data]

    def grad(self, var, **params):
        if var not in self.free_symbols:
            return Sum([], self.dom, self.cod)
        return Scalar(self.array[0].diff(var))

    def dagger(self):
        return self if self._dagger is None\
            else Scalar(self.array[0].conjugate())

    def conjugate(self):
        return Scalar(self.array[0].conjugate())

    l = r = property(conjugate)


class MixedScalar(Scalar):
    """ Mixed scalar, i.e. where the Born rule has already been applied. """
    def __init__(self, data):
        super().__init__(data, is_mixed=True)


class Sqrt(Scalar):
    """ Square root. """
    def __init__(self, data):
        super().__init__(data, name="sqrt")
        self.drawing_name = "sqrt({})".format(format_number(data))

    @property
    def array(self):
        return [self.data ** .5]


SWAP = Swap(qubit, qubit)
CZ = QuantumGate('CZ', 2, [1, 0, 0, 0,
                           0, 1, 0, 0,
                           0, 0, 1, 0,
                           0, 0, 0, -1], _dagger=None)
H = QuantumGate(
    'H', 1, 1 / numpy.sqrt(2) * numpy.array([1, 1, 1, -1]),
    _dagger=None, _conjugate=None)
S = QuantumGate('S', 1, [1, 0, 0, 1j])
T = QuantumGate('T', 1, [1, 0, 0, numpy.exp(1j * numpy.pi / 4)])
X = QuantumGate('X', 1, [0, 1, 1, 0], _dagger=None, _conjugate=None)
Y = QuantumGate('Y', 1, [0, -1j, 1j, 0], _dagger=None)
Z = QuantumGate('Z', 1, [1, 0, 0, -1], _dagger=None, _conjugate=None)
CX = Controlled(X)

GATES = [SWAP, CZ, CX, H, S, T, X, Y, Z]


def rewire(op, a: int, b: int, *, dom=None):
    """
    Rewire a two-qubits gate (circuit) to arbitrary qubits.
    :param a: The destination qubit index of the leftmost wire of the
    input gate.
    :param b: The destination qubit index of the rightmost wire of the
    input gate.
    :param dom: Optional domain/codomain for the resulting circuit.
    """
    if len(set([a, b])) != 2:
        raise ValueError('The destination indices must be distinct')
    dom = qubit ** (max(a, b) + 1) if dom is None else dom
    if len(dom) < 2:
        raise ValueError('Dom size expected at least 2')
    if op.dom != qubit**2:
        raise ValueError('Input gate\'s dom expected qubit**2')

    if (b - a) == 1:
        # a, b contiguous and not reversed
        return Box.id(a) @ op @ Box.id(len(dom) - (b + 1))
    if (b - a) == -1:
        # a, b contiguous and reversed
        op = (SWAP >> op >> SWAP) if op.cod == op.dom else (SWAP >> op)
        return Box.id(b) @ op @ Box.id(len(dom) - (a + 1))

    if op.cod != op.dom:
        raise NotImplementedError
    reverse = a > b
    a, b = min(a, b), max(a, b)
    perm = list(range(len(dom)))
    perm[0], perm[a] = a, 0
    perm[1], perm[b] = perm[b], perm[1]
    if reverse:
        perm[0], perm[1] = perm[1], perm[0]
    perm = Box.permutation(perm, dom=dom)
    return perm.dagger() >> (op @ Box.id(len(dom) - 2)) >> perm


def sqrt(expr):
    """ Returns a 0-qubit quantum gate that scales by a square root. """
    return Sqrt(expr)


def scalar(expr, is_mixed=False):
    """ Returns a 0-qubit quantum gate that scales by a complex number. """
    return Scalar(expr, is_mixed=is_mixed)
