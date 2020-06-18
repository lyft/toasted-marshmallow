from marshmallow import Schema, ValidationError

from .jit import (
    generate_marshall_method,
    generate_unmarshall_method,
    JitContext
)

__version__ = '2.15.2post1'


class JitMethodWrapper():
    use_cython = False

    def __init__(self, schema, method):
        self._schema = schema
        self._method = method

        self._jit_method = None
        self._prev_fields_dict = None

    def __call__(self, obj, fields_dict, many=False, **kwargs):
        self._ensure_jit_method(fields_dict)

        try:
            result = self._jit_method(obj, many=many)
        except (
                ValidationError,
                KeyError,
                AttributeError,
                ValueError,
                TypeError
        ):
            result = self._method(obj, fields_dict, many=many, **kwargs)

        return result

    def _ensure_jit_method(self, fields_dict):
        if not self._jit_method or fields_dict != self._prev_fields_dict:
            self._jit_method = self.generate_jit_method(
                self._schema,
                JitContext(use_cython=self.use_cython)
            )

        self._prev_fields_dict = fields_dict

    def generate_jit_method(self, schema, context):
        raise NotImplementedError()

    def __getattr__(self, item):
        return getattr(self._method, item)


class JitMarshal(JitMethodWrapper):
    def __init__(self, schema):
        super(JitMarshal, self).__init__(schema, schema._marshal)

    def generate_jit_method(self, schema, context):
        return generate_marshall_method(schema, context)


class JitUnmarshal(JitMethodWrapper):
    def __init__(self, schema):
        super(JitUnmarshal, self).__init__(schema, schema._unmarshal)

    def generate_jit_method(self, schema, context):
        return generate_unmarshall_method(schema, context)


class CythonJitMarshal(JitMarshal):
    use_cython = True


class CythonJitUnmarshal(JitUnmarshal):
    use_cython = True


class JitSchema(Schema):
    jit_marshal_class = JitMarshal
    jit_unmarshal_class = JitUnmarshal

    def __init__(self, *args, **kwargs):
        super(JitSchema, self).__init__(*args, **kwargs)

        self._marshal = self.jit_marshal_class(self)
        self._unmarshal = self.jit_unmarshal_class(self)


class CythonJitSchema(JitSchema):
    jit_marshal_class = CythonJitMarshal
    jit_unmarshal_class = CythonJitUnmarshal
