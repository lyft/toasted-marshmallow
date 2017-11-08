#!/usr/bin/env bash

cd marshmallow
pip install -U ../[reco]
pip install -U -r ../dev-requirements.txt
export MARSHMALLOW_SCHEMA_DEFAULT_JIT=toastedmarshmallow.Jit
invoke test
