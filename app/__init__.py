from flask import Flask
from flask_session import Session
from datetime import timedelta


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "change-this-in-production"
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    Session(app)

    from .routes import bp
    app.register_blueprint(bp)

    return app


