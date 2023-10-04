"""Benchmark for Marshmallow serialization of a moderately complex object.

"""

from __future__ import print_function, unicode_literals, division

import argparse
import cProfile
import gc
import time
import timeit
from marshmallow import Schema, fields, ValidationError
from deepfriedmarshmallow import JitSchema


# Custom validator
def must_not_be_blank(data):
    if not data:
        raise ValidationError("Data not provided.")


def create_quotes_schema(jit):
    SchemaBase = JitSchema if jit else Schema

    class AuthorSchema(SchemaBase):
        class Meta:
            jit_options = {
                "no_callable_fields": True,
            }

        id = fields.Int()
        first = fields.Str()
        last = fields.Str()
        book_count = fields.Float()
        age = fields.Float()
        address = fields.Str()
        deceased = fields.Boolean()

        def full_name(self, obj):
            return obj.first + " " + obj.last

        def format_name(self, author):
            return "{0}, {1}".format(author.last, author.first)

    class QuoteSchema(SchemaBase):
        class Meta:
            jit_options = {
                "no_callable_fields": True,
                "expected_marshal_type": "object",
            }

        id = fields.Int()
        author = fields.Nested(AuthorSchema)
        content = fields.Str(required=True)
        posted_at = fields.Int()
        book_name = fields.Str()
        page_number = fields.Float()
        line_number = fields.Float()
        col_number = fields.Float()
        is_verified = fields.Boolean()

    return QuoteSchema(many=True)


class Author:
    def __init__(self, id, first, last, book_count, age, address, deceased):
        self.id = id
        self.first = first
        self.last = last
        self.book_count = book_count
        self.age = age
        self.address = address
        self.deceased = deceased


class Quote:
    def __init__(self, id, author, content, posted_at, book_name, page_number, line_number, col_number, is_verified):
        self.id = id
        self.author = author
        self.content = content
        self.posted_at = posted_at
        self.book_name = book_name
        self.page_number = page_number
        self.line_number = line_number
        self.col_number = col_number
        self.is_verified = is_verified


def run_timeit(quotes, iterations, repeat, jit=False, load=False, profile=False):
    quotes_schema = create_quotes_schema(jit)
    if profile:
        profile = cProfile.Profile()
        profile.enable()
    dumped_quotes = quotes_schema.dump(quotes)
    gc.collect()

    if load:

        def marshmallow_func():
            quotes_schema.load(dumped_quotes, many=True)

    else:

        def marshmallow_func():
            quotes_schema.dump(quotes)

    best = min(timeit.repeat(marshmallow_func, "gc.enable()", number=iterations, repeat=repeat))
    if profile:
        profile.disable()
        file_name = "optimized.pprof" if jit else "original.pprof"
        profile.dump_stats(file_name)

    usec = best * 1e6 / iterations
    return usec


def main():
    parser = argparse.ArgumentParser(description="Runs a benchmark of Marshmallow.")
    parser.add_argument("--iterations", type=int, default=1000, help="Number of iterations to run per test.")
    parser.add_argument(
        "--repeat",
        type=int,
        default=5,
        help="Number of times to repeat the performance test. The minimum will be used.",
    )
    parser.add_argument("--object-count", type=int, default=20, help="Number of objects to dump.")
    parser.add_argument(
        "--profile", action="store_true", help="Whether or not to profile Marshmallow while running the benchmark."
    )
    args = parser.parse_args()

    quotes = []
    for i in range(args.object_count):
        quotes.append(
            Quote(
                i,
                Author(i, "Foo", "Bar", 42, 66, "123 Fake St", False),
                "Hello World",
                time.time(),
                "The World",
                34,
                3,
                70,
                False,
            )
        )

    print("Benchmark Result:")
    original_dump_time = run_timeit(quotes, args.iterations, args.repeat, load=False, jit=False, profile=args.profile)
    print("\tOriginal Dump Time: {0:.2f} usec/dump".format(original_dump_time))
    original_load_time = run_timeit(quotes, args.iterations, args.repeat, load=True, jit=False, profile=args.profile)
    print("\tOriginal Load Time: {0:.2f} usec/load".format(original_load_time))
    optimized_dump_time = run_timeit(quotes, args.iterations, args.repeat, load=False, jit=True, profile=args.profile)
    print("\tOptimized Dump Time: {0:.2f} usec/dump".format(optimized_dump_time))
    optimized_load_time = run_timeit(quotes, args.iterations, args.repeat, load=True, jit=True, profile=args.profile)
    print("\tOptimized Load Time: {0:.2f} usec/load".format(optimized_load_time))
    print("\tSpeed up for dump: {0:.2f}x".format(original_dump_time / optimized_dump_time))
    print("\tSpeed up for load: {0:.2f}x".format(original_load_time / optimized_load_time))


if __name__ == "__main__":
    main()
