import os

from dotenv import load_dotenv
from flask import Flask
from flask_sock import Sock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

sock = Sock()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
    app.config["DATABASE"] = os.path.join(app.instance_path, "..", "just_ralph_it.db")
    app.config["OPENCODE_URL"] = os.environ.get("OPENCODE_URL", "http://127.0.0.1:4096")
    app.config["GITHUB_CLIENT_ID"] = os.environ.get("GITHUB_CLIENT_ID", "")
    app.config["GITHUB_CLIENT_SECRET"] = os.environ.get("GITHUB_CLIENT_SECRET", "")
    app.config["VAPID_PRIVATE_KEY_PATH"] = os.environ.get(
        "VAPID_PRIVATE_KEY_PATH", os.path.join(PROJECT_ROOT, "vapid_private.pem")
    )
    app.config["VAPID_CLAIMS_EMAIL"] = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:admin@justralph.it")

    if test_config is not None:
        app.config.update(test_config)

    # Validate SECRET_KEY in non-test mode
    if not app.config.get("TESTING"):
        secret = app.config.get("SECRET_KEY")
        if not secret or secret == "dev":
            raise RuntimeError(
                "SECRET_KEY is not set or is insecure. Set a cryptographically secure SECRET_KEY in your .env file."
            )

    from . import auth, models, routes
    from .compaction import start_compaction_monitor
    from .recovery import recover_processes

    models.init_app(app)
    app.register_blueprint(routes.bp)
    app.register_blueprint(auth.bp)
    sock.init_app(app)

    recover_processes(app)

    # Start background session compaction monitor (skip in tests)
    if not app.config.get("TESTING"):
        start_compaction_monitor(app)

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
