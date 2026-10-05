"""Standalone setup harness for verifying storage before app integration."""

from flask import Flask

from . import init_storage


def create_app():
    app = Flask(__name__)
    init_storage(app)
    return app
