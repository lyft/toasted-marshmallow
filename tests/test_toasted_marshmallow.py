import pytest
from marshmallow import Schema, fields

import toastedmarshmallow


@pytest.fixture()
def schema():
    class TestSchema(Schema):
        key = fields.String(default='world')
        value = fields.Integer(missing=42)
    return TestSchema()


def test_marshmallow_integration_dump(schema):
    schema.jit = toastedmarshmallow.Jit
    assert schema._jit_instance is not None

    result = schema.dump({'key': 'hello', 'value': 32})
    assert not result.errors
    assert result.data == {'key': 'hello', 'value': 32}

    result = schema.dump({'value': 32})
    assert not result.errors
    assert result.data == {'key': 'world', 'value': 32}

    assert schema._jit_instance is not None


def test_marshmallow_integration_load(schema):
    schema.jit = toastedmarshmallow.Jit
    assert schema._jit_instance is not None

    result = schema.load({'key': 'hello', 'value': 32})
    assert not result.errors
    assert result.data == {'key': 'hello', 'value': 32}

    result = schema.load([{'key': 'hello'}], many=True)
    assert not result.errors
    assert result.data == [{'key': 'hello', 'value': 42}]
    assert schema._jit_instance is not None


def test_marshmallow_integration_invalid_data(schema):
    schema.jit = toastedmarshmallow.Jit
    assert schema._jit_instance is not None
    result = schema.dump({'key': 'hello', 'value': 'foo'})
    assert {'value': ['Not a valid integer.']} == result.errors
    result = schema.load({'key': 'hello', 'value': 'foo'})
    assert {'value': ['Not a valid integer.']} == result.errors
    assert schema._jit_instance is not None
