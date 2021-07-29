*************************************************************
:fire:toastedmarshmallow:fire:: Makes Marshmallow Toasty Fast
*************************************************************

Toasted Marshmallow implements a JIT for marshmallow that speeds up dumping
objects 10-25X (depending on your schema).  Toasted Marshmallow allows you to
have the great API that
`Marshmallow <https://github.com/marshmallow-code/marshmallow>`_ provides
without having to sacrifice performance!

::

    Benchmark Result:
      Original Time: 2682.61 usec/dump
      Optimized Time: 176.38 usec/dump
      Speed up: 15.21x

Even ``PyPy`` benefits from ``toastedmarshmallow``!

::

    Benchmark Result:
    	Original Time: 189.78 usec/dump
    	Optimized Time: 20.03 usec/dump
    	Speed up: 9.48x

Installing toastedmarshmallow
-----------------------------

.. code-block:: bash

  pip install toastedmarshmallow

This will *also* install a slightly-forked ``marshmallow`` that includes some
hooks Toastedmarshmallow needs enable the JIT to run before falling back
to the original marshmallow code.  These changes are minimal making it easier
to track upstream.  You can find the changes
`Here <https://github.com/marshmallow-code/marshmallow/pull/629/files>`_.

This means you should **remove** ``marshmallow`` from your requirements and
replace it with ``toastedmarshmallow``.  By default there is no
difference unless you explicitly enable Toasted Marshmallow.

Enabling Toasted Marshmallow
----------------------------

Enabling Toasted Marshmallow on an existing Schema is just one line of code,
set the ``jit`` property on any ``Schema`` instance to 
``toastedmarshmallow.Jit``.  For example:

.. code-block:: python

    from datetime import date
    import toastedmarshmallow
    from marshmallow import Schema, fields, pprint

    class ArtistSchema(Schema):
        name = fields.Str()

    class AlbumSchema(Schema):
        title = fields.Str()
        release_date = fields.Date()
        artist = fields.Nested(ArtistSchema())

    schema = AlbumSchema()
    # Specify the jit method as toastedmarshmallow's jit
    schema.jit = toastedmarshmallow.Jit
    # And that's it!  Your dump methods are 15x faster!

It's also possible to use the ``Meta`` class on the ``Marshmallow`` schema
to specify all instances of a given ``Schema`` should be optimized:

.. code-block:: python

    import toastedmarshmallow
    from marshmallow import Schema, fields, pprint

    class ArtistSchema(Schema):
        class Meta:
            jit = toastedmarshmallow.Jit
        name = fields.Str()

You can also enable Toasted Marshmallow globally by setting the environment
variable ``MARSHMALLOW_SCHEMA_DEFAULT_JIT`` to ``toastedmarshmallow.Jit`` .
Future versions of Toasted Marshmallow may make this the default.

How it works
------------

Toasted Marshmallow works by generating code at runtime to optimize dumping
objects without going through layers and layers of reflection.  The generated
code optimistically assumes the objects being passed in are schematically valid,
falling back to the original marshmallow code on failure.

For example, taking ``AlbumSchema`` from above, Toastedmarshmallow will
generate the following 3 methods:

.. code-block:: python

    def InstanceSerializer(obj):
        res = {}
        value = obj.release_date; value = value() if callable(value) else value; res["release_date"] = _field_release_date__serialize(value, "release_date", obj)
        value = obj.artist; value = value() if callable(value) else value; res["artist"] = _field_artist__serialize(value, "artist", obj)
        value = obj.title; value = value() if callable(value) else value; value = str(value) if value is not None else None; res["title"] = value
        return res

    def DictSerializer(obj):
        res = {}
        if "release_date" in obj:
            value = obj["release_date"]; value = value() if callable(value) else value; res["release_date"] = _field_release_date__serialize(value, "release_date", obj)
        if "artist" in obj:
            value = obj["artist"]; value = value() if callable(value) else value; res["artist"] = _field_artist__serialize(value, "artist", obj)
        if "title" in obj:
            value = obj["title"]; value = value() if callable(value) else value; value = str(value) if value is not None else None; res["title"] = value
        return res

    def HybridSerializer(obj):
        res = {}
        try:
            value = obj["release_date"]
        except (KeyError, AttributeError, IndexError, TypeError):
            value = obj.release_date
        value = value; value = value() if callable(value) else value; res["release_date"] = _field_release_date__serialize(value, "release_date", obj)
        try:
            value = obj["artist"]
        except (KeyError, AttributeError, IndexError, TypeError):
            value = obj.artist
        value = value; value = value() if callable(value) else value; res["artist"] = _field_artist__serialize(value, "artist", obj)
        try:
            value = obj["title"]
        except (KeyError, AttributeError, IndexError, TypeError):
            value = obj.title
        value = value; value = value() if callable(value) else value; value = str(value) if value is not None else None; res["title"] = value
        return res

Toastedmarshmallow will invoke the proper serializer based upon the input.

Since Toastedmarshmallow is generating code at runtime, it's critical you
re-use Schema objects.  If you're creating a new Schema object every time you
serialize/deserialize an object you'll likely have much worse performance.
