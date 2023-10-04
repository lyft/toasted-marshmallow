from marshmallow import fields
from deepfriedmarshmallow import JitSchema
from deepfriedmarshmallow.jit import JitContext, generate_method_bodies


class ArtistSchema(JitSchema):
    name = fields.Str()


class AlbumSchema(JitSchema):
    title = fields.Str()
    release_date = fields.Date()
    artist = fields.Nested(ArtistSchema())


schema = AlbumSchema()

if __name__ == "__main__":
    print(generate_method_bodies(schema, JitContext()))
