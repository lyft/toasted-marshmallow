import pytest
from marshmallow import Schema, fields, ValidationError

import deepfriedmarshmallow


@pytest.fixture()
def schema():
    class TestSchema(deepfriedmarshmallow.JitSchema):
        key = fields.String(dump_default="world")
        value = fields.Integer(load_default=42)

    return TestSchema()


def test_marshmallow_integration_dump(schema):
    result = schema.dump({"key": "hello", "value": 32})
    assert result == {"key": "hello", "value": 32}

    result = schema.dump({"value": 32})
    assert result == {"key": "world", "value": 32}


def test_marshmallow_integration_load(schema):
    result = schema.load({"key": "hello", "value": 32})
    assert result == {"key": "hello", "value": 32}

    result = schema.load([{"key": "hello"}], many=True)
    assert result == [{"key": "hello", "value": 42}]


def test_marshmallow_integration_invalid_data(schema):
    with pytest.raises(ValueError, match="invalid literal for int\(\) with base 10"):
        schema.dump({"key": "hello", "value": "foo"})
    with pytest.raises(ValidationError, match="Not a valid integer"):
        schema.load({"key": "hello", "value": "foo"})
