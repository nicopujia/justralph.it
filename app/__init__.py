import os

from flask import Flask

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
    app.config["DATABASE"] = os.path.join(app.instance_path, "..", "just_ralph_it.db")
    app.config["OPENCODE_URL"] = os.environ.get("OPENCODE_URL", "http://127.0.0.1:4096")
    app.config["GITHUB_APP_ID"] = int(os.environ.get("GITHUB_APP_ID", "0"))
    app.config["GITHUB_APP_SLUG"] = "just-ralph-it"
    app.config["GITHUB_PRIVATE_KEY_PATH"] = os.path.join(PROJECT_ROOT, "just-ralph-it.2026-03-14.private-key.pem")

    if test_config is not None:
        app.config.update(test_config)

    from . import auth, models, routes
    from .recovery import recover_processes

    models.init_app(app)
    app.register_blueprint(routes.bp)
    app.register_blueprint(auth.bp)

    recover_processes(app)

    return app
