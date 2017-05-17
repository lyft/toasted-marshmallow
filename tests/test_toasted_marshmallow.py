import pytest
from marshmallow import Schema, fields

import toastedmarshmallow


@pytest.fixture()
def schema():
    class TestSchema(Schema):
        key = fields.String()
        value = fields.Integer()
    return TestSchema()


def test_marshmallow_integration(schema):
    schema.jit = toastedmarshmallow.Jit
    assert schema._jit_instance is not None
    result = schema.dump({'key': 'hello', 'value': 32})
    assert not result.errors
    assert result.data == {'key': 'hello', 'value': 32}
    assert schema._jit_instance is not None


def test_marshmallow_integration_invalid_data(schema):
    schema.jit = toastedmarshmallow.Jit
    assert schema._jit_instance is not None
    result = schema.dump({'key': 'hello', 'value': 'foo'})
    assert {'value': ['Not a valid integer.']} == result.errors
    assert schema._jit_instance is not None
