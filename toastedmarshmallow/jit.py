import base64
import keyword
import platform
import re
from abc import ABCMeta, abstractmethod
from collections import Mapping

import attr
from six import exec_, iteritems, add_metaclass, text_type
from marshmallow import missing, Schema, fields
from marshmallow.base import SchemaABC

from .compat import is_overridden
from .utils import IndentedString


CYTHON_AVAILABLE = False
if platform.python_implementation() == 'CPython':
    try:
        import cython
        CYTHON_AVAILABLE = True
    except ImportError:
        cython = None


# Regular Expression for identifying a valid Python identifier name.
_VALID_IDENTIFIER = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')

if False:  # pylint: disable=using-constant-test
    # pylint: disable=unused-import
    from typing import Any, Callable, Dict, List, Optional, Union, Set


def field_symbol_name(field_name):
    # type: (str) -> str
    """Generates the symbol name to be used when accessing a field in generated
    code.

    If the field name isn't a valid identifier name, syntesizes a name by
    base64 encoding the fieldname.
    """
    if not _VALID_IDENTIFIER.match(field_name):
        field_name = str(base64.b64encode(
            field_name.encode('utf-8')).decode('utf-8').strip('='))
    return '_field_{field_name}'.format(field_name=field_name)


def attr_str(attr_name):
    # type: (str) -> str
    """Gets the string to use when accessing an attribute on an object.

    Handles case where tje attribute name collides with a keyword and would
    therefore be illegal to access with dot notation.
    """
    if keyword.iskeyword(attr_name):
        return 'getattr(obj, "{0}")'.format(attr_name)
    return 'obj.{0}'.format(attr_name)


@add_metaclass(ABCMeta)
class FieldSerializer(object):
    """Base class for generating code to serialize a field.
    """
    @abstractmethod
    def serialize(self, attr_name, field_symbol,
                  assignment_template, field_obj):
        # type: (str, str, str, fields.Field) -> IndentedString
        pass


class InstanceSerializer(FieldSerializer):
    """Generates code for accessing fields as if they were instance variables.
    """
    def serialize(self, attr_name, field_symbol,
                  assignment_template, field_obj):
        # type: (str, str, str, fields.Field) -> IndentedString
        return IndentedString(assignment_template.format(attr_str(attr_name)))


class DictSerializer(FieldSerializer):
    """Generates code for accessing fields as if they were a dict.
    """
    def serialize(self, attr_name, field_symbol,
                  assignment_template, field_obj):
        # type: (str, str, str, fields.Field) -> IndentedString
        body = IndentedString()
        if field_obj.default == missing:
            body += 'if "{attr_name}" in obj:'.format(attr_name=attr_name)
            with body.indent():
                body += assignment_template.format('obj["{attr_name}"]'.format(
                    attr_name=attr_name))
        else:
            default_str = 'default'
            if callable(field_obj.default):
                default_str = 'default()'
            body += assignment_template.format(
                'obj.get("{attr_name}", {field_symbol}__{default_str})'.format(
                    attr_name=attr_name, field_symbol=field_symbol,
                    default_str=default_str))
        return body


class HybridSerializer(FieldSerializer):
    """Generates code for accessing fields as if they were a hybrid object.

    Hybrid objects are objets that don't inherit from `Mapping`, but do
    implement `__getitem__`.  This means we first have to attempt a lookup by
    key, then fall back to looking up by instance variable.
    """
    def serialize(self, attr_name, field_symbol,
                  assignment_template, field_obj):
        # type: (str, str, str, fields.Field) -> IndentedString
        body = IndentedString()
        body += 'try:'
        with body.indent():
            body += 'value = obj["{attr_name}"]'.format(attr_name=attr_name)
        body += 'except (KeyError, AttributeError, IndexError, TypeError):'
        with body.indent():
            body += 'value = {attr_str}'.format(attr_str=attr_str(attr_name))
        body += assignment_template.format('value')
        return body


@attr.s
class JitContext(object):
    namespace = attr.ib(default={})  # type: Dict[str, Any]
    use_cython = attr.ib(default=False)  # type: bool
    schema_stack = attr.ib(default=attr.Factory(set))  # type: Set[str]
    additional_method_bodies = attr.ib(
        default=attr.Factory(list))  # type: List[str]
    only = attr.ib(default=None)
    exclude = attr.ib(default=set())


@add_metaclass(ABCMeta)
class FieldInliner(object):
    """Base class for generating code to serialize a field.
    """
    @abstractmethod
    def inline(self, field, context):
        # type: (fields.Field, JitContext) -> Optional[str]
        pass


class StringInliner(FieldInliner):
    def inline(self, field, context):
        # type: (fields.Field, JitContext) -> Optional[str]
        """Generates a template for inlining string serialization.

        For example, generates "unicode(value) if value is not None else None"
        to serialize a string in Python 2.7
        """
        if is_overridden(field._serialize, fields.String._serialize):
            return None
        result = text_type.__name__ + '({0})'
        return result + ' if {0} is not None else None'


class BooleanInliner(FieldInliner):
    def inline(self, field, context):
        # type: (fields.Field, JitContext) -> Optional[str]
        """Generates a template for inlining string serialization.

        For example, generates "float(value) if value is not None else None"
        to serialize a float.  If `field.as_string` is `True` the result will
        be coerced to a string if not None.
        """
        if is_overridden(field._serialize, fields.Boolean._serialize):
            return None
        truthy_symbol = '__{0}_truthy'.format(field.name)
        falsy_symbol = '__{0}_falsy'.format(field.name)
        context.namespace[truthy_symbol] = field.truthy
        context.namespace[falsy_symbol] = field.falsy
        result = ('(({0} in ' + truthy_symbol +
                  ') or (False if {0} in ' + falsy_symbol +
                  ' else bool({0})))')
        return result + ' if {0} is not None else None'


class NumberInliner(FieldInliner):
    def inline(self, field, context):
        # type: (fields.Field, JitContext) -> Optional[str]
        """Generates a template for inlining string serialization.

        For example, generates "float(value) if value is not None else None"
        to serialize a float.  If `field.as_string` is `True` the result will
        be coerced to a string if not None.
        """
        if (is_overridden(field._validated, fields.Number._validated) or
                is_overridden(field._serialize, fields.Number._serialize)):
            return None
        result = field.num_type.__name__ + '({0})'
        if field.as_string:
            result = 'str({0})'.format(result)
        return result + ' if {0} is not None else None'


class NestedInliner(FieldInliner):
    def inline(self, field, context):
        # type: (fields.Field, JitContext) -> Optional[str]
        """Generates a template for inlining nested field.

        This doesn't pass tests yet in Marshmallow, namely due to issues around
        code expecting the context of nested schema to be populated on first
        access, so disabling for now.
        """
        if is_overridden(field._serialize, fields.Nested._serialize):
            return None

        if not (isinstance(field.nested, type) and
                issubclass(field.nested, SchemaABC)):
            return None

        if field.nested.__class__ in context.schema_stack:
            return None

        method_name = '__nested_{}_serialize'.format(
            field_symbol_name(field.name))

        old_only = context.only
        old_exclude = context.exclude
        old_namespace = context.namespace

        context.only = set(field.only) if field.only else None
        context.exclude = set(field.exclude)
        context.namespace = {}

        for only_field in old_only or []:
            if only_field.startswith(field.name + '.'):
                if not context.only:
                    context.only = set()
                context.only.add(only_field[len(field.name + '.'):])
        for only_field in list((context.only or [])):
            if '.' in only_field:
                if not context.only:
                    context.only = set()
                context.only.add(only_field.split('.')[0])

        for exclude_field in old_exclude:
            if exclude_field.startswith(field.name + '.'):
                context.exclude.add(exclude_field[len(field.name + '.'):])

        serialize_method = generate_marshall_method(field.schema, context)
        if serialize_method is None:
            return None

        context.namespace = old_namespace
        context.only = old_only
        context.exclude = old_exclude

        context.namespace[method_name] = serialize_method

        if field.many:
            return ('[' + method_name +
                    '(_x) for _x in {0}] if {0} is not None else None')
        return method_name + '({0}) if {0} is not None else None'


INLINERS = {
    fields.String: StringInliner(),
    fields.Number: NumberInliner(),
    fields.Boolean: BooleanInliner(),
}

EXPECTED_TYPE_TO_CLASS = {
    'object': InstanceSerializer,
    'dict': DictSerializer,
    'hybrid': HybridSerializer
}


def generate_marshall_method_body(schema, on_field, context):
    # type: (Schema, FieldSerializer, JitContext) -> IndentedString
    """Generates the method body for a schema and a given field serialization
    strategy.
    """
    body = IndentedString()
    body += 'def {method_name}(obj):'.format(
        method_name=on_field.__class__.__name__)
    with body.indent():
        jit_options = getattr(schema.opts, 'jit_options', {})
        if schema.dict_class is dict:
            # Declaring dictionaries via `{}` is faster than `dict()`
            body += 'res = {}'
        else:
            body += 'res = dict_class()'
        for field_name, field_obj in iteritems(schema.fields):
            if getattr(field_obj, 'load_only', False):
                continue
            if context.only and field_name not in context.only:
                continue
            if context.exclude and field_name in context.exclude:
                continue
            key = ''.join(
                [schema.prefix or '', field_obj.dump_to or field_name])
            attr_name = field_name
            if field_obj.attribute:
                attr_name = field_obj.attribute
            field_symbol = field_symbol_name(field_name)
            assignment_template = ''
            value_key = '{0}'

            # If we have to assume any field can be callable we always have to
            # check to see if we need to invoke the method first.
            # We can investigate tracing this as well.
            if not jit_options.get('no_callable_fields'):
                assignment_template = (
                    'value = {0}; '
                    'value = value() if callable(value) else value; ')
                value_key = 'value'

            # Attempt to see if this field type can be inlined.
            inliner = None
            for field_type, inliner_class in iteritems(INLINERS):
                if isinstance(field_obj, field_type):
                    inliner = inliner_class.inline(field_obj, context)
                    if inliner:
                        break

            if inliner:
                value_key = 'value'
                if not jit_options.get('no_callable_fields'):
                    assignment_template += 'value = {0}; '.format(
                        inliner.format(value_key))
                else:
                    assignment_template += 'value = {0}; '
                    value_key = inliner.format('value')
                assignment_template += 'res["{key}"] = {value_key}'.format(
                    key=key, value_key=value_key)

            else:
                assignment_template += (
                    'res["{key}"] = {field_symbol}__serialize('
                    '{value_key}, "{field_name}", obj)'.format(
                        key=key, field_symbol=field_symbol,
                        field_name=field_name, value_key=value_key))
            if not field_obj._CHECK_ATTRIBUTE:
                # fields like 'Method' expect to have `None` passed in when
                # invoking their _serialize method.
                body += assignment_template.format('None')
            elif _VALID_IDENTIFIER.match(attr_name):
                body += on_field.serialize(attr_name, field_symbol,
                                           assignment_template, field_obj)
            else:
                # If attr_name is not a valid python identifier, it can only
                # be accessed via key lookups.
                body += DictSerializer().serialize(
                    attr_name, field_symbol, assignment_template, field_obj)
        body += 'return res'
    return body


def generate_marshall_method_bodies(schema, context):
    # type: (Schema, JitContext) -> str
    """Generate 3 method bodies for marshalling objects, dictionaries, or hybrid
    objects.
    """
    result = IndentedString()

    result += generate_marshall_method_body(schema,
                                            InstanceSerializer(),
                                            context)
    result += generate_marshall_method_body(schema,
                                            DictSerializer(),
                                            context)
    result += generate_marshall_method_body(schema,
                                            HybridSerializer(),
                                            context)
    return str(result)


class SerializeProxy(object):
    """Proxy object for calling serializer methods.

    Initially trace calls to serialize and if the number of calls
    of a specific type crosses `threshold` swaps out the implementation being
    used for the most specialized one available.
    """
    def __init__(self, dict_serializer, hybrid_serializer,
                 instance_serializer,
                 threshold=100):
        # type: (Callable, Callable, Callable, int) -> None
        self.dict_serializer = dict_serializer
        self.hybrid_serializer = hybrid_serializer
        self.instance_serializer = instance_serializer
        self.threshold = threshold
        self.dict_count = 0
        self.hybrid_count = 0
        self.instance_count = 0
        self._call = self.tracing_call

        if not threshold:
            self._call = self.no_tracing_call

    def __call__(self, obj):
        return self._call(obj)

    def tracing_call(self, obj):
        # type: (Any) -> Any
        """Dispatcher which traces calls and specializes if possible.
        """
        try:
            if isinstance(obj, Mapping):
                self.dict_count += 1
                return self.dict_serializer(obj)
            elif hasattr(obj, '__getitem__'):
                self.hybrid_count += 1
                return self.hybrid_serializer(obj)
            self.instance_count += 1
            return self.instance_serializer(obj)
        finally:
            non_zeros = [x for x in
                         [self.dict_count,
                          self.hybrid_count,
                          self.instance_count] if x > 0]
            if len(non_zeros) > 1:
                self._call = self.no_tracing_call
            elif self.dict_count >= self.threshold:
                self._call = self.dict_serializer
            elif self.hybrid_count >= self.threshold:
                self._call = self.hybrid_serializer
            elif self.instance_count >= self.threshold:
                self._call = self.instance_serializer

    def no_tracing_call(self, obj):
        # type: (Any) -> Any
        """Dispatcher with no tracing.
        """
        if isinstance(obj, Mapping):
            return self.dict_serializer(obj)
        elif hasattr(obj, '__getitem__'):
            return self.hybrid_serializer(obj)
        return self.instance_serializer(obj)


def generate_marshall_method(schema, context=missing, threshold=100):
    # type: (Schema, JitContext, int) -> Union[SerializeProxy, Callable, None]
    """Generates a function to marshall objects for a given schema.

    :param schema: The Schema to generate a marshall method for.
    :param threshold: The number of calls of the same type to observe before
        specializing the marshal method for that type.
    :param use_cython: Whether or not to attempt to use cython when Jitting.
    :return: A Callable that can be used to marshall objects for the schema
    """
    if is_overridden(schema.get_attribute, Schema.get_attribute):
        # Bail if get_attribute is overridden
        return None

    if context is missing:
        context = JitContext()

    context.namespace['dict_class'] = lambda: schema.dict_class()  # pylint: disable=unnecessary-lambda

    jit_options = getattr(schema.opts, 'jit_options', {})

    context.schema_stack.add(schema.__class__)
    result = generate_marshall_method_bodies(schema, context)
    result += '\n\n' + '\n\n'.join(context.additional_method_bodies)
    context.additional_method_bodies = []
    context.schema_stack.remove(schema.__class__)

    namespace = context.namespace

    for key, value in iteritems(schema.fields):
        namespace[field_symbol_name(key) + '__serialize'] = value._serialize
        if value.default is not missing:
            namespace[field_symbol_name(key) + '__default'] = value.default

    if context.use_cython and CYTHON_AVAILABLE:
        namespace = cython.inline(result, **namespace)
    else:
        exec_(result, namespace)

    proxy = None  # type: Optional[SerializeProxy]
    marshall_method = None  # type: Union[SerializeProxy, Callable, None]
    if jit_options.get('expected_marshal_type') in EXPECTED_TYPE_TO_CLASS:
        marshall_method = namespace[EXPECTED_TYPE_TO_CLASS[
            jit_options['expected_marshal_type']].__name__]
    else:
        marshall_method = SerializeProxy(
            namespace[DictSerializer.__name__],
            namespace[HybridSerializer.__name__],
            namespace[InstanceSerializer.__name__],
            threshold=threshold)
        proxy = marshall_method

    def marshall(obj, many=False):
        if many:
            return [marshall_method(x) for x in obj]
        return marshall_method(obj)

    if proxy:
        marshall.proxy = proxy  # type: ignore
    return marshall
