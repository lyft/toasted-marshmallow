from toastedmarshmallow.utils import IndentedString


def test_indented_string():
    body = IndentedString()
    subbody = IndentedString('if False:')

    with subbody.indent():
        subbody += 'print("How are you?")'

    body += 'def foo():'
    with body.indent():
        body += 'print("Hello World!")'
        body += subbody

    assert str(body) == ('def foo():\n'
                         '    print("Hello World!")\n'
                         '    if False:\n'
                         '        print("How are you?")')
