import pytest
from marshmallow import fields

import toastedmarshmallow


@pytest.fixture(params=[
    toastedmarshmallow.JitSchema,
    toastedmarshmallow.CythonJitSchema,
])
def schema(request):
    class TestSchema(request.param):
        key = fields.String(default='world')
        value = fields.Integer(missing=42)
    return TestSchema()


def test_marshmallow_integration_dump(schema):
    result = schema.dump({'key': 'hello', 'value': 32})
    assert not result.errors
    assert result.data == {'key': 'hello', 'value': 32}

    result = schema.dump({'value': 32})
    assert not result.errors
    assert result.data == {'key': 'world', 'value': 32}


def test_marshmallow_integration_load(schema):
    result = schema.load({'key': 'hello', 'value': 32})
    assert not result.errors
    assert result.data == {'key': 'hello', 'value': 32}

    result = schema.load([{'key': 'hello'}], many=True)
    assert not result.errors
    assert result.data == [{'key': 'hello', 'value': 42}]


def test_marshmallow_integration_invalid_data(schema):
    result = schema.dump({'key': 'hello', 'value': 'foo'})
    assert {'value': ['Not a valid integer.']} == result.errors

    result = schema.load({'key': 'hello', 'value': 'foo'})
    assert {'value': ['Not a valid integer.']} == result.errors
