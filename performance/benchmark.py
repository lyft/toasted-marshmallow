"""Benchmark for Marshmallow serialization of a moderately complex object.

"""

from __future__ import print_function, unicode_literals, division

import argparse
import cProfile
import gc
import timeit
import time

import benchmark_pb2
from marshmallow import Schema, fields, ValidationError, pre_load
from toastedmarshmallow import CythonJit, Jit


# Custom validator
def must_not_be_blank(data):
    if not data:
        raise ValidationError('Data not provided.')


class AuthorSchema(Schema):
    class Meta:
        jit_options = {
            'no_callable_fields': True,
            'expected_marshal_type': 'object',
        }
    id = fields.Int(dump_only=True)
    first = fields.Str()
    last = fields.Str()
    book_count = fields.Float()
    age = fields.Float()
    address = fields.Str()
    deceased = fields.Boolean()

    def full_name(self, obj):
        return obj.first + ' ' + obj.last

    def format_name(self, author):
        return "{0}, {1}".format(author.last, author.first)


class QuoteSchema(Schema):
    class Meta:
        jit_options = {
            'no_callable_fields': True,
            'expected_marshal_type': 'object',
        }

    id = fields.Int(dump_only=True)
    author = fields.Nested(AuthorSchema)
    content = fields.Str(required=True)
    posted_at = fields.Int(dump_only=True)
    book_name = fields.Str()
    page_number = fields.Float()
    line_number = fields.Float()
    col_number = fields.Float()
    is_verified = fields.Boolean()

    @pre_load
    def process_author(self, data):
        author_name = data.get('author')
        if author_name:
            first, last = author_name.split(' ')
            author_dict = dict(first=first, last=last)
        else:
            author_dict = {}
        data['author'] = author_dict
        return data


class Author(object):
    def __init__(self, id, first, last, book_count, age, address, deceased):
        self.id = id
        self.first = first
        self.last = last
        self.book_count = book_count
        self.age = age
        self.address = address
        self.deceased = deceased


class Quote(object):
    def __init__(self, id, author, content, posted_at, book_name, page_number,
                 line_number, col_number, is_verified):
        self.id = id
        self.author = author
        self.content = content
        self.posted_at = posted_at
        self.book_name = book_name
        self.page_number = page_number
        self.line_number = line_number
        self.col_number = col_number
        self.is_verified = is_verified


def run_timeit(quotes, iterations, repeat, quotes_proto=None,
               jit=False, cython=False, profile=False):
    quotes_schema = QuoteSchema(many=True)
    if jit:
        if cython:
            quotes_schema.jit = CythonJit
        else:
            quotes_schema.jit = Jit
    if profile:
        profile = cProfile.Profile()
        profile.enable()

    gc.collect()

    def marshmallow_func():
        quotes_schema.dump(quotes)

    def proto_func():
        quotes_proto.SerializeToString()
    if quotes_proto:
        func = proto_func
    else:
        func = marshmallow_func

    best = min(timeit.repeat(func,
                             'gc.enable()',
                             number=iterations,
                             repeat=repeat))
    if profile:
        profile.disable()
        file_name = 'optimized.pprof' if jit else 'original.pprof'
        if quotes_proto:
            file_name = 'proto.pprof'
        profile.dump_stats(file_name)

    usec = best * 1e6 / iterations
    return usec


def main():
    parser = argparse.ArgumentParser(
        description='Runs a benchmark of Marshmallow.')
    parser.add_argument('--iterations', type=int, default=1000,
                        help='Number of iterations to run per test.')
    parser.add_argument('--repeat', type=int, default=5,
                        help='Number of times to repeat the performance test. '
                             'The minimum will be used.')
    parser.add_argument('--object-count', type=int, default=20,
                        help='Number of objects to dump.')
    parser.add_argument('--profile', action='store_true',
                        help='Whether or not to profile Marshmallow while '
                             'running the benchmark.')
    args = parser.parse_args()

    quotes = []
    quote_protos = benchmark_pb2.Quotes()

    for i in range(args.object_count):
        quotes.append(
            Quote(i, Author(i, 'Foo', 'Bar', 42, 66, '123 Fake St', False),
                  'Hello World', time.time(), 'The World', 34, 3, 70, False)
        )
        quote_pb = quote_protos.quotes.add()
        quote_pb.id = i
        quote_pb.content = 'Hello World'
        quote_pb.posted_at = int(time.time())
        quote_pb.book_name = 'The World'
        quote_pb.page_number = 34
        quote_pb.line_number = 3
        quote_pb.col_number = 70
        author_pb = quote_pb.author
        author_pb.id = i
        author_pb.first = 'Foo'
        author_pb.last = 'Bar'
        author_pb.book_count = 42
        author_pb.age = 66
        author_pb.address = '123 Fake St'

    original_time = run_timeit(quotes, args.iterations, args.repeat,
                               jit=False, profile=args.profile)
    proto_time = run_timeit(quotes, args.iterations, args.repeat,
                            quotes_proto=quote_protos,
                            jit=False, profile=args.profile)
    optimized_time = run_timeit(quotes, args.iterations, args.repeat,
                                jit=True, profile=args.profile)
    cython_time = run_timeit(quotes, args.iterations, args.repeat,
                             jit=True, cython=True, profile=args.profile)
    print('Benchmark Result:')
    print('\tOriginal Time: {0:.2f} usec/dump'.format(original_time))
    print('\tProto Time: {0:.2f} usec/dump'.format(proto_time))
    print('\tOptimized Time: {0:.2f} usec/dump'.format(optimized_time))
    print('\tOptimized (Cython) Time: {0:.2f} usec/dump'.format(cython_time))
    print('\tSpeed up: {0:.2f}x'.format(original_time / optimized_time))
    print('\tCython Speed up: {0:.2f}x'.format(original_time / cython_time))
    print('\tCython Speed up over Python Jit: {0:.2f}x'.format(
        optimized_time / cython_time))


if __name__ == '__main__':
    main()
