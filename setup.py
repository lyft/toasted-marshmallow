#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
from setuptools import setup


EXTRA_REQUIREMENTS = ['python-dateutil', 'simplejson']


def find_version(fname):
    """Attempts to find the version number in the file names fname.
    Raises RuntimeError if not found.
    """
    version = ''
    with open(fname, 'r') as fp:
        reg = re.compile(r'__version__ = [\'"]([^\'"]*)[\'"]')
        for line in fp:
            m = reg.match(line)
            if m:
                version = m.group(1)
                break
    if not version:
        raise RuntimeError('Cannot find version information')
    return version


__version__ = find_version("toastedmarshmallow/__init__.py")


def read(fname):
    with open(fname) as fp:
        content = fp.read()
    return content


setup(
    name='toastedmarshmallow',
    version=__version__,
    description=('A JIT implementation for Marshmallow to speed up '
                 'dumping and loading objects.'),
    long_description=read('README.rst'),
    author='Roy Williams',
    author_email='rwilliams@lyft.com',
    url='https://github.com/lyft/toasted-marshmallow',
    packages=['toastedmarshmallow', 'marshmallow'],
    package_dir={
        'toastedmarshmallow': 'toastedmarshmallow',
        'marshmallow': 'marshmallow/marshmallow'
    },
    include_package_data=True,
    extras_require={'reco': EXTRA_REQUIREMENTS},
    license='apache2',
    install_requires=[
        'attrs >= 17.1.0'
    ],
    zip_safe=False,
    keywords=(
        'serialization', 'rest', 'json', 'api', 'marshal',
        'marshalling', 'deserialization', 'validation', 'schema'
    ),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    test_suite='tests'
)
