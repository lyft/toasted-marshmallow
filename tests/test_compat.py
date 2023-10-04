from deepfriedmarshmallow.compat import is_overridden


class Base(object):
    def foo(self):
        pass


class NoOverride(Base):
    pass


class HasOverride(Base):
    def foo(self):
        pass


def test_is_overridden():
    assert is_overridden(HasOverride().foo, Base.foo)
    assert not is_overridden(NoOverride().foo, Base.foo)
