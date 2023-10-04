import pytest
from marshmallow import fields, Schema
from six import text_type

from deepfriedmarshmallow.jit import (
    attr_str,
    field_symbol_name,
    InstanceSerializer,
    DictSerializer,
    HybridSerializer,
    generate_transform_method_body,
    generate_method_bodies,
    generate_serialize_method,
    generate_deserialize_method,
    JitContext,
)


@pytest.fixture()
def simple_schema():
    class InstanceSchema(Schema):
        key = fields.String()
        value = fields.Integer(dump_default=0)

    return InstanceSchema()


@pytest.fixture()
def nested_circular_ref_schema():
    class NestedStringSchema(Schema):
        key = fields.String()
        me = fields.Nested("NestedStringSchema")

    return NestedStringSchema()


@pytest.fixture()
def nested_schema():
    class GrandChildSchema(Schema):
        bar = fields.String()
        raz = fields.String()

    class SubSchema(Schema):
        name = fields.String()
        value = fields.Nested(GrandChildSchema)

    class NestedSchema(Schema):
        key = fields.String()
        value = fields.Nested(SubSchema, only=("name", "value.bar"))
        values = fields.Nested(SubSchema, exclude=("value",), many=True)

    return NestedSchema()


@pytest.fixture()
def optimized_schema():
    class OptimizedSchema(Schema):
        class Meta:
            jit_options = {"no_callable_fields": True, "expected_serialize_type": "object"}

        key = fields.String()
        value = fields.Integer(dump_default=0, as_string=True)

    return OptimizedSchema()


@pytest.fixture()
def simple_object():
    class InstanceObject(object):
        def __init__(self):
            self.key = "some_key"
            self.value = 42

    return InstanceObject()


@pytest.fixture()
def simple_dict():
    return {"key": "some_key", "value": 42}


@pytest.fixture()
def simple_hybrid():
    class HybridObject(object):
        def __init__(self):
            self.key = "some_key"

        def __getitem__(self, item):
            if item == "value":
                return 42
            raise KeyError()

    return HybridObject()


@pytest.fixture()
def schema():
    class BasicSchema(Schema):
        class Meta:
            ordered = True

        foo = fields.Integer(attribute="@#")
        bar = fields.String()
        raz = fields.Method("raz_")
        meh = fields.String(load_only=True)
        blargh = fields.Boolean()

        def raz_(self, obj):
            return "Hello!"

    return BasicSchema()


class RoundedFloat(fields.Float):
    def __init__(self, places, **kwargs):
        super(fields.Float, self).__init__(**kwargs)
        self.num_type = lambda x: round(x, places)


@pytest.fixture
def non_primitive_num_type_schema():
    class NonPrimitiveNumTypeSchema(Schema):
        gps_longitude = RoundedFloat(places=6, attribute="lng")

    return NonPrimitiveNumTypeSchema()


def test_field_symbol_name():
    assert "_field_hello" == field_symbol_name("hello")
    assert "_field_MHdvcmxkMA" == field_symbol_name("0world0")


def test_attr_str():
    assert "obj.foo" == attr_str("foo")
    assert 'getattr(obj, "def")' == attr_str("def")


def test_instance_serializer():
    serializer = InstanceSerializer()
    field = fields.Integer()
    assert 'result["foo"] = obj.foo' == str(serializer.serialize("foo", "bar", 'result["foo"] = {0}', field))


def test_dict_serializer_with_default():
    serializer = DictSerializer()
    field = fields.Integer(dump_default=3)
    result = str(serializer.serialize("foo", "bar", 'result["foo"] = {0}', field))
    assert 'result["foo"] = obj.get("foo", bar__dump_default)' == result


def test_dict_serializer_with_callable_default():
    serializer = DictSerializer()
    field = fields.Integer(dump_default=int)
    result = str(serializer.serialize("foo", "bar", 'result["foo"] = {0}', field))
    assert 'result["foo"] = obj.get("foo", bar__dump_default())' == result


def test_dict_serializer_no_default():
    serializer = DictSerializer()
    field = fields.Integer()
    result = str(serializer.serialize("foo", "bar", 'result["foo"] = {0}', field))
    expected = 'if "foo" in obj:\n    result["foo"] = obj["foo"]'
    assert expected == result


def test_hybrid_serializer():
    serializer = HybridSerializer()
    field = fields.Integer()
    result = str(serializer.serialize("foo", "bar", 'result["foo"] = {0}', field))
    expected = (
        "try:\n"
        '    value = obj["foo"]\n'
        "except (KeyError, AttributeError, IndexError, TypeError):\n"
        "    value = obj.foo\n"
        'result["foo"] = value'
    )
    assert expected == result


def test_generate_serialize_method_body(schema):
    expected_start = """\
def InstanceSerializer(obj):
    res = dict_class()
"""
    raz_assignment = (
        "value = None; "
        "value = value() if callable(value) else value; "
        'res["raz"] = _field_raz__serialize(value, "raz", obj)'
    )

    foo_assignment = (
        'if "@#" in obj:\n'
        '        value = obj["@#"]; value = value() if callable(value) else value; '
        'res["foo"] = _field_foo__serialize(value, "foo", obj)'
    )
    bar_assignment = (
        "value = obj.bar; "
        "value = value() if callable(value) else value; "
        "value = {text_type}(value) if value is not None else None; "
        'res["bar"] = value'
    ).format(text_type=text_type.__name__)
    blargh_assignment = (
        "value = obj.blargh; "
        "value = value() if callable(value) else value; "
        "value = ((value in __blargh_truthy) or "
        '(False if value in __blargh_falsy else dict()["error"])) '
        "if value is not None else None; "
        'res["blargh"] = value'
    )

    context = JitContext()
    result = str(generate_transform_method_body(schema, InstanceSerializer(), context))
    assert result.startswith(expected_start)
    assert raz_assignment in result
    assert foo_assignment in result
    assert bar_assignment in result
    assert blargh_assignment in result
    assert "meh" not in result
    assert result.endswith("return res")


def test_generate_serialize_method_bodies():
    class OneFieldSchema(Schema):
        foo = fields.Integer()

    context = JitContext()
    result = generate_method_bodies(OneFieldSchema(), context)
    expected = """\
def InstanceSerializer(obj):
    res = {}
    value = obj.foo; value = value() if callable(value) else value; \
res["foo"] = _field_foo__serialize(value, "foo", obj)
    return res
def DictSerializer(obj):
    res = {}
    if "foo" in obj:
        value = obj["foo"]; value = value() if callable(value) else value; \
res["foo"] = _field_foo__serialize(value, "foo", obj)
    return res
def HybridSerializer(obj):
    res = {}
    try:
        value = obj["foo"]
    except (KeyError, AttributeError, IndexError, TypeError):
        value = obj.foo
    value = value; value = value() if callable(value) else value; res["foo"] = _field_foo__serialize(value, "foo", obj)
    return res"""
    assert expected == result


def test_generate_deserialize_method_bodies():
    class OneFieldSchema(Schema):
        foo = fields.Integer()

    context = JitContext(is_serializing=False, use_inliners=False)
    result = generate_method_bodies(OneFieldSchema(), context)
    expected = """\
def InstanceSerializer(obj):
    res = {}
    __res_get = res.get
    res["foo"] = _field_foo__deserialize(obj.foo, "foo", obj)
    if __res_get("foo", res) is None:
        raise ValueError()
    return res
def DictSerializer(obj):
    res = {}
    __res_get = res.get
    if "foo" in obj:
        res["foo"] = _field_foo__deserialize(obj["foo"], "foo", obj)
    if __res_get("foo", res) is None:
        raise ValueError()
    return res
def HybridSerializer(obj):
    res = {}
    __res_get = res.get
    try:
        value = obj["foo"]
    except (KeyError, AttributeError, IndexError, TypeError):
        value = obj.foo
    res["foo"] = _field_foo__deserialize(value, "foo", obj)
    if __res_get("foo", res) is None:
        raise ValueError()
    return res"""
    assert expected == result


def test_generate_deserialize_method_bodies_with_load_from():
    class OneFieldSchema(Schema):
        foo = fields.Integer(metadata={"load_from": "bar"}, allow_none=True)

    context = JitContext(is_serializing=False, use_inliners=False)
    result = str(generate_transform_method_body(OneFieldSchema(), DictSerializer(context), context))
    expected = """\
def DictSerializer(obj):
    res = {}
    __res_get = res.get
    if "foo" in obj:
        res["foo"] = _field_foo__deserialize(obj["foo"], "foo", obj)
    return res"""
    assert expected == result


def test_generate_deserialize_method_bodies_required():
    class OneFieldSchema(Schema):
        foo = fields.Integer(required=True)

    context = JitContext(is_serializing=False, use_inliners=False)
    result = str(generate_transform_method_body(OneFieldSchema(), DictSerializer(context), context))
    expected = """\
def DictSerializer(obj):
    res = {}
    __res_get = res.get
    res["foo"] = _field_foo__deserialize(obj["foo"], "foo", obj)
    if "foo" not in res:
        raise ValueError()
    if __res_get("foo", res) is None:
        raise ValueError()
    return res"""
    assert expected == result


def test_jit_bails_with_get_attribute():
    class DynamicSchema(Schema):
        def get_attribute(self, obj, attr, default):
            pass

    serialize_method = generate_serialize_method(DynamicSchema())
    assert serialize_method is None


def test_jit_bails_nested_attribute():
    class DynamicSchema(Schema):
        foo = fields.String(attribute="foo.bar")

    serialize_method = generate_serialize_method(DynamicSchema())
    assert serialize_method is None


def test_jitted_serialize_method(schema):
    context = JitContext()
    serialize_method = generate_serialize_method(schema, threshold=1, context=context)
    result = serialize_method({"@#": 32, "bar": "Hello", "meh": "Foo"})
    expected = {"bar": "Hello", "foo": 32, "raz": "Hello!"}
    assert expected == result
    # Test specialization
    result = serialize_method({"@#": 32, "bar": "Hello", "meh": "Foo"})
    assert expected == result
    assert serialize_method.proxy._call == serialize_method.proxy.dict_serializer


def test_non_primitive_num_type_schema(non_primitive_num_type_schema):
    context = JitContext()
    serialize_method = generate_serialize_method(non_primitive_num_type_schema, threshold=1, context=context)
    result = serialize_method({})
    expected = {}
    assert expected == result


def test_jitted_deserialize_method(schema):
    context = JitContext()
    deserialize_method = generate_deserialize_method(schema, context=context)
    result = deserialize_method({"foo": 32, "bar": "Hello", "meh": "Foo"})
    expected = {"bar": "Hello", "@#": 32, "meh": "Foo"}
    assert expected == result

    assert not hasattr(deserialize_method, "proxy")


def test_jitted_serialize_method_bails_on_specialize(simple_schema, simple_object, simple_dict, simple_hybrid):
    serialize_method = generate_serialize_method(simple_schema, threshold=2)
    assert simple_dict == serialize_method(simple_dict)
    assert serialize_method.proxy._call == serialize_method.proxy.tracing_call
    assert simple_dict == serialize_method(simple_object)
    assert serialize_method.proxy._call == serialize_method.proxy.no_tracing_call
    assert simple_dict == serialize_method(simple_object)
    assert serialize_method.proxy._call == serialize_method.proxy.no_tracing_call
    assert simple_dict == serialize_method(simple_dict)
    assert serialize_method.proxy._call == serialize_method.proxy.no_tracing_call
    assert simple_dict == serialize_method(simple_hybrid)
    assert serialize_method.proxy._call == serialize_method.proxy.no_tracing_call


def test_dict_jitted_serialize_method(simple_schema):
    serialize_method = generate_serialize_method(simple_schema)
    result = serialize_method({"key": "some_key"})
    expected = {"key": "some_key", "value": 0}
    assert expected == result


def test_jitted_serialize_method_no_threshold(simple_schema, simple_dict):
    serialize_method = generate_serialize_method(simple_schema, threshold=0)
    assert serialize_method.proxy._call == serialize_method.proxy.no_tracing_call
    result = serialize_method(simple_dict)
    assert simple_dict == result
    assert serialize_method.proxy._call == serialize_method.proxy.no_tracing_call


def test_hybrid_jitted_serialize_method(simple_schema, simple_hybrid, simple_dict):
    serialize_method = generate_serialize_method(simple_schema, threshold=1)
    result = serialize_method(simple_hybrid)
    assert simple_dict == result
    result = serialize_method(simple_hybrid)
    assert simple_dict == result
    assert serialize_method.proxy._call == serialize_method.proxy.hybrid_serializer


def test_instance_jitted_instance_serialize_method(simple_schema, simple_object, simple_dict):
    serialize_method = generate_serialize_method(simple_schema, threshold=1)
    result = serialize_method(simple_object)
    assert simple_dict == result
    result = serialize_method(simple_object)
    assert simple_dict == result
    assert serialize_method.proxy._call == serialize_method.proxy.instance_serializer


def test_instance_jitted_instance_serialize_method_supports_none_int(simple_schema, simple_object):
    simple_object.value = None
    serialize_method = generate_serialize_method(simple_schema)
    result = serialize_method(simple_object)
    expected = {"key": "some_key", "value": None}
    assert expected == result


def test_optimized_jitted_serialize_method(optimized_schema, simple_object):
    serialize_method = generate_serialize_method(optimized_schema)
    result = serialize_method(simple_object)
    expected = {"key": "some_key", "value": "42"}
    assert expected == result


def test_nested_serialize_method_circular_ref(nested_circular_ref_schema):
    serialize_method = generate_serialize_method(nested_circular_ref_schema)
    result = serialize_method({"key": "some_key", "me": {"key": "sub_key"}})
    expected = {"key": "some_key", "me": {"key": "sub_key"}}
    assert expected == result


def test_nested_serialize_method(nested_schema):
    serialize_method = generate_serialize_method(nested_schema)
    result = serialize_method(
        {
            "key": "some_key",
            "value": {"name": "sub_key", "value": {"bar": "frob", "raz": "blah"}},
            "values": [{"name": "first_child", "value": "foo"}, {"name": "second_child", "value": "bar"}],
        }
    )
    expected = {
        "key": "some_key",
        "value": {"name": "sub_key", "value": {"bar": "frob"}},
        "values": [
            {
                "name": "first_child",
            },
            {"name": "second_child"},
        ],
    }
    assert expected == result
