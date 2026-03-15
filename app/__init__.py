import os

from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
    app.config["DATABASE"] = os.path.join(app.instance_path, "..", "just_ralph_it.db")

    from . import routes

    app.register_blueprint(routes.bp)

    return app
