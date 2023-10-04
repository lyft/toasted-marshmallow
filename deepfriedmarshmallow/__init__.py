from marshmallow import Schema, ValidationError

from .jit import JitContext, generate_deserialize_method, generate_serialize_method

__version__ = "1.0.0dev1"


class JitMethodWrapper:
    def __init__(self, schema, method):
        self._schema = schema
        self._method = method

        self._jit_method = None
        self._prev_fields_dict = None

    def __call__(self, obj, many=False, **kwargs):  # noqa: FBT002
        self._ensure_jit_method()

        try:
            result = self._jit_method(obj, many=many)
        except (ValidationError, KeyError, AttributeError, ValueError, TypeError):
            result = self._method(obj, many=many, **kwargs)

        return result

    def _ensure_jit_method(self):
        if self._jit_method is None:
            self._jit_method = self.generate_jit_method(self._schema, JitContext())

    def generate_jit_method(self, schema, context):
        raise NotImplementedError

    def __getattr__(self, item):
        return getattr(self._method, item)


class JitSerialize(JitMethodWrapper):
    def __init__(self, schema):
        super().__init__(schema, schema._serialize)

    def generate_jit_method(self, schema, context):
        return generate_serialize_method(schema, context)


class JitDeserialize(JitMethodWrapper):
    def __init__(self, schema):
        super().__init__(schema, schema._deserialize)

    def generate_jit_method(self, schema, context):
        return generate_deserialize_method(schema, context)


class JitSchema(Schema):
    jit_serialize_class = JitSerialize
    jit_deserialize_class = JitDeserialize

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._serialize = self.jit_serialize_class(self)
        self._deserialize = self.jit_deserialize_class(self)
