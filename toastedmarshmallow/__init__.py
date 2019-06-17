from marshmallow import SchemaJit

from .jit import (
    generate_marshall_method,
    generate_unmarshall_method,
    JitContext
)

__version__ = '2.15.1'


class Jit(SchemaJit):
    def __init__(self, schema):
        super(Jit, self).__init__(schema)
        self.schema = schema
        self.marshal_method = generate_marshall_method(
            schema, context=JitContext())
        self.unmarshal_method = generate_unmarshall_method(
            schema, context=JitContext())

    @property
    def jitted_marshal_method(self):
        return self.marshal_method

    @property
    def jitted_unmarshal_method(self):
        return self.unmarshal_method
