import os

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
    app.config["DATABASE"] = os.path.join(app.instance_path, "..", "just_ralph_it.db")

    if test_config is not None:
        app.config.update(test_config)

    from . import models, routes

    models.init_app(app)
    app.register_blueprint(routes.bp)

    return app
