import pytest
from marshmallow import fields, Schema
from six import text_type

from toastedmarshmallow.jit import (
    attr_str, field_symbol_name, InstanceSerializer, DictSerializer,
    HybridSerializer,
    generate_transform_method_body, generate_method_bodies,
    generate_marshall_method, generate_unmarshall_method, JitContext)


@pytest.fixture()
def simple_schema():
    class InstanceSchema(Schema):
        key = fields.String()
        value = fields.Integer(default=0)
    return InstanceSchema()


@pytest.fixture()
def nested_circular_ref_schema():
    class NestedStringSchema(Schema):
        key = fields.String()
        me = fields.Nested('NestedStringSchema')
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
        value = fields.Nested(SubSchema, only=('name', 'value.bar'))
        values = fields.Nested(SubSchema, exclude=('value', ), many=True)
    return NestedSchema()


@pytest.fixture()
def optimized_schema():
    class OptimizedSchema(Schema):
        class Meta:
            jit_options = {
                'no_callable_fields': True,
                'expected_marshal_type': 'object'
            }
        key = fields.String()
        value = fields.Integer(default=0, as_string=True)
    return OptimizedSchema()


@pytest.fixture()
def simple_object():
    class InstanceObject(object):
        def __init__(self):
            self.key = 'some_key'
            self.value = 42
    return InstanceObject()


@pytest.fixture()
def simple_dict():
    return {
        'key': u'some_key',
        'value': 42
    }


@pytest.fixture()
def simple_hybrid():
    class HybridObject(object):
        def __init__(self):
            self.key = 'some_key'

        def __getitem__(self, item):
            if item == 'value':
                return 42
            raise KeyError()
    return HybridObject()


@pytest.fixture()
def schema():
    class BasicSchema(Schema):
        class Meta:
            ordered = True
        foo = fields.Integer(attribute='@#')
        bar = fields.String()
        raz = fields.Method('raz_')
        meh = fields.String(load_only=True)
        blargh = fields.Boolean()

        def raz_(self, obj):
            return 'Hello!'
    return BasicSchema()


def test_field_symbol_name():
    assert '_field_hello' == field_symbol_name('hello')
    assert '_field_MHdvcmxkMA' == field_symbol_name('0world0')


def test_attr_str():
    assert 'obj.foo' == attr_str('foo')
    assert 'getattr(obj, "def")' == attr_str('def')


def test_instance_serializer():
    serializer = InstanceSerializer()
    field = fields.Integer()
    assert 'result["foo"] = obj.foo' == str(serializer.serialize(
        'foo', 'bar', 'result["foo"] = {0}', field))


def test_dict_serializer_with_default():
    serializer = DictSerializer()
    field = fields.Integer(default=3)
    result = str(serializer.serialize('foo', 'bar', 'result["foo"] = {0}',
                                      field))
    assert 'result["foo"] = obj.get("foo", bar__default)' == result


def test_dict_serializer_with_callable_default():
    serializer = DictSerializer()
    field = fields.Integer(default=int)
    result = str(serializer.serialize('foo', 'bar', 'result["foo"] = {0}',
                                      field))
    assert 'result["foo"] = obj.get("foo", bar__default())' == result


def test_dict_serializer_no_default():
    serializer = DictSerializer()
    field = fields.Integer()
    result = str(serializer.serialize('foo', 'bar', 'result["foo"] = {0}',
                                      field))
    expected = ('if "foo" in obj:\n'
                '    result["foo"] = obj["foo"]')
    assert expected == result


def test_hybrid_serializer():
    serializer = HybridSerializer()
    field = fields.Integer()
    result = str(serializer.serialize('foo', 'bar', 'result["foo"] = {0}',
                                      field))
    expected = ('try:\n'
                '    value = obj["foo"]\n'
                'except (KeyError, AttributeError, IndexError, TypeError):\n'
                '    value = obj.foo\n'
                'result["foo"] = value')
    assert expected == result


def test_generate_marshall_method_body(schema):
    expected_start = '''\
def InstanceSerializer(obj):
    res = dict_class()
'''
    raz_assignment = ('value = None; '
                      'value = value() if callable(value) else value; '
                      'res["raz"] = _field_raz__serialize(value, "raz", obj)')

    foo_assignment = (
        'if "@#" in obj:\n'
        '        value = obj["@#"]; '
        'value = value() if callable(value) else value; '
        'value = int(value) if value is not None else None; '
        'res["foo"] = value')
    bar_assignment = (
        'value = obj.bar; '
        'value = value() if callable(value) else value; '
        'value = {text_type}(value) if value is not None else None; '
        'res["bar"] = value').format(text_type=text_type.__name__)
    blargh_assignment = (
        'value = obj.blargh; '
        'value = value() if callable(value) else value; '
        'value = ((value in __blargh_truthy) or '
        '(False if value in __blargh_falsy else bool(value))) '
        'if value is not None else None; '
        'res["blargh"] = value')

    context = JitContext()
    result = str(generate_transform_method_body(schema,
                                                InstanceSerializer(),
                                                context))
    assert result.startswith(expected_start)
    assert raz_assignment in result
    assert foo_assignment in result
    assert bar_assignment in result
    assert blargh_assignment in result
    assert 'meh' not in result
    assert result.endswith('return res')


def test_generate_marshall_method_bodies():
    class OneFieldSchema(Schema):
        foo = fields.Integer()
    context = JitContext()
    result = generate_method_bodies(OneFieldSchema(), context)
    expected = '''\
def InstanceSerializer(obj):
    res = {}
    value = obj.foo; value = value() if callable(value) else value; \
value = int(value) if value is not None else None; res["foo"] = value
    return res
def DictSerializer(obj):
    res = {}
    if "foo" in obj:
        value = obj["foo"]; value = value() if callable(value) else value; \
value = int(value) if value is not None else None; res["foo"] = value
    return res
def HybridSerializer(obj):
    res = {}
    try:
        value = obj["foo"]
    except (KeyError, AttributeError, IndexError, TypeError):
        value = obj.foo
    value = value; value = value() if callable(value) else value; \
value = int(value) if value is not None else None; res["foo"] = value
    return res'''
    assert expected == result


def test_generate_unmarshall_method_bodies():
    class OneFieldSchema(Schema):
        foo = fields.Integer()
    context = JitContext(is_serializing=False, use_inliners=False)
    result = generate_method_bodies(OneFieldSchema(), context)
    expected = '''\
def InstanceSerializer(obj):
    res = {}
    res["foo"] = _field_foo__deserialize(obj.foo, "foo", obj)
    return res
def DictSerializer(obj):
    res = {}
    if "foo" in obj:
        res["foo"] = _field_foo__deserialize(obj["foo"], "foo", obj)
    return res
def HybridSerializer(obj):
    res = {}
    try:
        value = obj["foo"]
    except (KeyError, AttributeError, IndexError, TypeError):
        value = obj.foo
    res["foo"] = _field_foo__deserialize(value, "foo", obj)
    return res'''
    assert expected == result


def test_generate_unmarshall_method_bodies_with_load_from():
    class OneFieldSchema(Schema):
        foo = fields.Integer(load_from='bar')
    context = JitContext(is_serializing=False, use_inliners=False)
    result = str(generate_transform_method_body(OneFieldSchema(),
                                                DictSerializer(context),
                                                context))
    expected = '''\
def DictSerializer(obj):
    res = {}
    if "foo" in obj:
        res["foo"] = _field_foo__deserialize(obj["foo"], "bar", obj)
    if "foo" not in res:
        if "bar" in obj:
            res["foo"] = _field_foo__deserialize(obj["bar"], "bar", obj)
    return res'''
    assert expected == result


def test_generate_unmarshall_method_bodies_required():
    class OneFieldSchema(Schema):
        foo = fields.Integer(required=True)
    context = JitContext(is_serializing=False, use_inliners=False)
    result = str(generate_transform_method_body(OneFieldSchema(),
                                                DictSerializer(context),
                                                context))
    expected = '''\
def DictSerializer(obj):
    res = {}
    res["foo"] = _field_foo__deserialize(obj["foo"], "foo", obj)
    return res'''
    assert expected == result


def test_jit_bails_with_get_attribute():
    class DynamicSchema(Schema):
        def get_attribute(self, obj, attr, default):
            pass
    marshal_method = generate_marshall_method(DynamicSchema())
    assert marshal_method is None


def test_jit_bails_nested_attribute():
    class DynamicSchema(Schema):
        foo = fields.String(attribute='foo.bar')

    marshal_method = generate_marshall_method(DynamicSchema())
    assert marshal_method is None


@pytest.mark.parametrize('use_cython', [True, False])
def test_jitted_marshal_method(schema, use_cython):
    context = JitContext(use_cython=use_cython)
    marshal_method = generate_marshall_method(schema, threshold=1,
                                              context=context)
    result = marshal_method({
        '@#': 32,
        'bar': 'Hello',
        'meh': 'Foo'
    })
    expected = {
        'bar': u'Hello',
        'foo': 32,
        'raz': 'Hello!'
    }
    assert expected == result
    # Test specialization
    result = marshal_method({
        '@#': 32,
        'bar': 'Hello',
        'meh': 'Foo'
    })
    assert expected == result
    assert marshal_method.proxy._call == marshal_method.proxy.dict_serializer


@pytest.mark.parametrize('use_cython', [True, False])
def test_jitted_unmarshal_method(schema, use_cython):
    context = JitContext(use_cython=use_cython)
    unmarshal_method = generate_unmarshall_method(schema, context=context)
    result = unmarshal_method({
        'foo': 32,
        'bar': 'Hello',
        'meh': 'Foo'
    })
    expected = {
        'bar': u'Hello',
        '@#': 32,
        'meh': 'Foo'
    }
    assert expected == result

    assert not hasattr(unmarshal_method, 'proxy')


def test_jitted_marshal_method_bails_on_specialize(simple_schema,
                                                   simple_object,
                                                   simple_dict,
                                                   simple_hybrid):
    marshal_method = generate_marshall_method(simple_schema, threshold=2)
    assert simple_dict == marshal_method(simple_dict)
    assert marshal_method.proxy._call == marshal_method.proxy.tracing_call
    assert simple_dict == marshal_method(simple_object)
    assert marshal_method.proxy._call == marshal_method.proxy.no_tracing_call
    assert simple_dict == marshal_method(simple_object)
    assert marshal_method.proxy._call == marshal_method.proxy.no_tracing_call
    assert simple_dict == marshal_method(simple_dict)
    assert marshal_method.proxy._call == marshal_method.proxy.no_tracing_call
    assert simple_dict == marshal_method(simple_hybrid)
    assert marshal_method.proxy._call == marshal_method.proxy.no_tracing_call


def test_dict_jitted_marshal_method(simple_schema):
    marshal_method = generate_marshall_method(simple_schema)
    result = marshal_method({'key': 'some_key'})
    expected = {
        'key': 'some_key',
        'value': 0
    }
    assert expected == result


def test_jitted_marshal_method_no_threshold(simple_schema, simple_dict):
    marshal_method = generate_marshall_method(simple_schema, threshold=0)
    assert marshal_method.proxy._call == marshal_method.proxy.no_tracing_call
    result = marshal_method(simple_dict)
    assert simple_dict == result
    assert marshal_method.proxy._call == marshal_method.proxy.no_tracing_call


def test_hybrid_jitted_marshal_method(simple_schema,
                                      simple_hybrid,
                                      simple_dict):
    marshal_method = generate_marshall_method(simple_schema, threshold=1)
    result = marshal_method(simple_hybrid)
    assert simple_dict == result
    result = marshal_method(simple_hybrid)
    assert simple_dict == result
    assert marshal_method.proxy._call == marshal_method.proxy.hybrid_serializer


def test_instance_jitted_instance_marshal_method(simple_schema,
                                                 simple_object,
                                                 simple_dict):
    marshal_method = generate_marshall_method(simple_schema, threshold=1)
    result = marshal_method(simple_object)
    assert simple_dict == result
    result = marshal_method(simple_object)
    assert simple_dict == result
    assert (marshal_method.proxy._call ==
            marshal_method.proxy.instance_serializer)


def test_optimized_jitted_marshal_method(optimized_schema, simple_object):
    marshal_method = generate_marshall_method(optimized_schema)
    result = marshal_method(simple_object)
    expected = {
        'key': 'some_key',
        'value': '42'
    }
    assert expected == result


def test_nested_marshal_method_circular_ref(nested_circular_ref_schema):
    marshal_method = generate_marshall_method(nested_circular_ref_schema)
    result = marshal_method({
        'key': 'some_key',
        'me': {
            'key': 'sub_key'
        }
    })
    expected = {
        'key': 'some_key',
        'me': {
            'key': 'sub_key'
        }
    }
    assert expected == result


def test_nested_marshal_method(nested_schema):
    marshal_method = generate_marshall_method(nested_schema)
    result = marshal_method({
        'key': 'some_key',
        'value': {
            'name': 'sub_key',
            'value': {
                'bar': 'frob',
                'raz': 'blah'
            }
        },
        'values': [
            {
                'name': 'first_child',
                'value': 'foo'
            },
            {
                'name': 'second_child',
                'value': 'bar'
            }
        ]
    })
    expected = {
        'key': 'some_key',
        'value': {
            'name': 'sub_key',
            'value': {
                'bar': 'frob'
            }
        },
        'values': [
            {
                'name': 'first_child',
            },
            {
                'name': 'second_child'
            }
        ]
    }
    assert expected == result
