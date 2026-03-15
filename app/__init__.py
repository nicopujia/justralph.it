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
    app.config["VAPID_PRIVATE_KEY_PATH"] = os.environ.get(
        "VAPID_PRIVATE_KEY_PATH", os.path.join(PROJECT_ROOT, "vapid_private.pem")
    )
    app.config["VAPID_CLAIMS_EMAIL"] = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:admin@justralph.it")

    if test_config is not None:
        app.config.update(test_config)

    from . import auth, models, routes
    from .recovery import recover_processes

    models.init_app(app)
    app.register_blueprint(routes.bp)
    app.register_blueprint(auth.bp)

    recover_processes(app)

    # Compute VAPID application server key from public key file (unless already set by test_config)
    if "VAPID_APPLICATION_SERVER_KEY" not in app.config:
        vapid_pub_path = os.path.join(PROJECT_ROOT, "vapid_public.pem")
        if os.path.isfile(vapid_pub_path):
            try:
                import base64

                from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
                from py_vapid import Vapid

                vapid = Vapid.from_file(app.config["VAPID_PRIVATE_KEY_PATH"])
                raw = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
                app.config["VAPID_APPLICATION_SERVER_KEY"] = base64.urlsafe_b64encode(raw).decode().rstrip("=")
            except Exception:
                app.config["VAPID_APPLICATION_SERVER_KEY"] = ""
        else:
            app.config["VAPID_APPLICATION_SERVER_KEY"] = ""

    return app
