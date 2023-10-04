:fire: Deep-Fried Marshmallow – Makes Marshmallow a Chicken Nugget
==================================================================

I need to be honest with you — I have no idea how to compare the speed of a
marshmallow and the speed of a chicken nugget. I really liked that headline,
though, so let's just assume that a nugget is indeed faster than a 
marshmallow. So is this project, Deep-Fried Marshmallow, faster than 
vanilla Marshmallow. Or, to be precise, it *makes* Marshmallow faster.

Deep-Fried Marshmallow implements a JIT for Marshmallow that speeds up dumping
objects 3-5x (depending on your schema). Deep-Fried Marshmallow allows you to
have the great API that 
[Marshmallow](https://github.com/marshmallow-code/marshmallow) provides
without having to sacrifice performance.
```
    Benchmark Result:
        Original Dump Time: 220.50 usec/dump
        Original Load Time: 536.51 usec/load
        Optimized Dump Time: 58.67 usec/dump
        Optimized Load Time: 118.44 usec/load

        Speed up for dump: 3.76x
        Speed up for load: 4.53x
```

Deep-Fried Marshmallow is a fork of the great 
[Toasted Marshmallow](https://github.com/lyft/toasted-marshmallow) project that,
sadly, has been abandoned for years. Deep-Fried Marshmallow introduces many
changes that make it compatible with all latest versions of Marshmallow (3.13+).
It also changes the way the library interacts with Marshmallow, which means
that code of Marshmallow doesn't need to be forked and modified for the JIT
magic to work. That's a whole new level of magic!



## Installing Deep-Fried Marshmallow


```bash
pip install DeepFriedMarshmallow
# or, if your project uses Poetry:
poetry install DeepFriedMarshmallow
```

If your project doesn't have vanilla Marshmallow specified in requirements,
the latest version of it will be installed alongside Deep-Fried Marshmallow.
You are free to pin any version of it that you need, as long as it's
newer than v3.13.


## Enabling Deep-Fried Marshmallow

Enabling Deep-Fried Marshmallow on an existing schema is just one change of code. Change your schemas to inherit from the `JitSchema` class in the `deepfriedmarshmallow` package instead of `Schema` from `marshmallow`.

For example, this block of code:

```python
from marshmallow import Schema, fields

class ArtistSchema(Schema):
    name = fields.Str()

class AlbumSchema(Schema):
    title = fields.Str()
    release_date = fields.Date()
    artist = fields.Nested(ArtistSchema())

schema = AlbumSchema()
```

Should become this:
```python
from marshmallow import fields
from deepfriedmarshmallow import JitSchema

class ArtistSchema(JitSchema):
    name = fields.Str()

class AlbumSchema(JitSchema):
    title = fields.Str()
    release_date = fields.Date()
    artist = fields.Nested(ArtistSchema())

schema = AlbumSchema()
```

And that's it!

## How it works

Deep-Fried Marshmallow works by generating code at runtime to optimize dumping
objects without going through layers and layers of reflection. The generated
code optimistically assumes the objects being passed in are schematically valid,
falling back to the original Marshmallow code on failure.

For example, taking `AlbumSchema` from above, Deep-Fried Marshmallow will
generate the following methods:

```python
def InstanceSerializer(obj):
    res = {}
    value = obj.title; value = value() if callable(value) else value; value = str(value) if value is not None else None; res["title"] = value
    value = obj.release_date; value = value() if callable(value) else value; res["release_date"] = _field_release_date__serialize(value, "release_date", obj)
    value = obj.artist; value = value() if callable(value) else value; res["artist"] = _field_artist__serialize(value, "artist", obj)
    return res

def DictSerializer(obj):
    res = {}
    if "title" in obj:
        value = obj["title"]; value = value() if callable(value) else value; value = str(value) if value is not None else None; res["title"] = value
    if "release_date" in obj:
        value = obj["release_date"]; value = value() if callable(value) else value; res["release_date"] = _field_release_date__serialize(value, "release_date", obj)
    if "artist" in obj:
        value = obj["artist"]; value = value() if callable(value) else value; res["artist"] = _field_artist__serialize(value, "artist", obj)
    return res

def HybridSerializer(obj):
    res = {}
    try:
        value = obj["title"]
    except (KeyError, AttributeError, IndexError, TypeError):
        value = obj.title
    value = value; value = value() if callable(value) else value; value = str(value) if value is not None else None; res["title"] = value
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
    return res
```

Deep-Fried Marshmallow will invoke the proper serializer based upon the input.

Since Deep-Fried Marshmallow generates code at runtime, it's critical you
re-use Schema objects. If you're creating a new Schema object every time you
serialize or deserialize an object, you're likely to experience much worse 
performance.

## Special thanks to
 * [@rowillia](https://github.com/rowillia)/[@lyft](https://github.com/lyft) — for creating Toasted Marshmallow
 * [@taion](https://github.com/taion) — for a [PoC](https://github.com/lyft/toasted-marshmallow/pull/16) of injecting the JIT compiler by replacing the marshaller
 * [@Kalepa](https://github.com/Kalepa) — for needing improved Marshmallow performance so that I could actually work on this project 😅

## License
See [LICENSE](/LICENSE) for details.

## Contributing

Contributions, issues and feature requests are welcome!

Feel free to check [existing issues](https://github.com/mLupine/DeepFriedMarshmallow/issues) before reporting a new one.

## Show your support
Give this repository a ⭐️ if this project helped you!
