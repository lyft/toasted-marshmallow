from marshmallow import SchemaJit

from .jit import generate_marshall_method, JitContext

__version__ = '0.1.0'


class Jit(SchemaJit):
    def __init__(self, schema, use_cython=False):
        super(Jit, self).__init__(schema)
        self.schema = schema
        self.marshal_method = generate_marshall_method(
            schema, context=JitContext(use_cython=use_cython))
        self.unmarshal_method = None

    @property
    def jitted_marshal_method(self):
        return self.marshal_method

    @property
    def jitted_unmarshal_method(self):
        return self.unmarshal_method


class CythonJit(Jit):
    def __init__(self, schema):
        super(CythonJit, self).__init__(schema, use_cython=True)
