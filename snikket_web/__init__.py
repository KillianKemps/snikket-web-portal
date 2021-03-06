import base64
import binascii

from datetime import datetime, timedelta

import quart.flask_patch

from quart import (
    Quart, session, request, render_template, redirect, url_for, Response,
    current_app,
)

from flask_babel import Babel

from . import colour
from .prosodyclient import client

from ._version import version, version_info

app = Quart(__name__)
app.config.setdefault("LANGUAGES", ["de", "en"])
app.config.from_envvar("SNIKKET_WEB_CONFIG")

client.init_app(app)
client.default_login_redirect = "login"

babel = Babel(app)


@babel.localeselector
def selected_locale():
    return request.accept_languages.best_match(
        current_app.config['LANGUAGES']
    )


@app.route("/login", methods=["GET", "POST"])
async def login():
    if client.has_session and (await client.test_session()):
        return redirect(url_for('user.index'))

    if request.method == "POST":
        form = await request.form
        jid = form["address"]
        password = form["password"]
        await client.login(jid, password)
        return redirect(url_for('user.index'))

    return await render_template("login.html")


@app.route("/")
async def home():
    if client.has_session:
        return redirect(url_for('user.index'))

    return redirect(url_for('login'))


@app.route("/meta/about.html")
async def about():
    return await render_template("about.html", version=version)


@app.route("/meta/demo.html")
async def demo():
    return await render_template("demo.html")


def repad(s):
    return s + "=" * (4 - len(s) % 4)


@app.route("/avatar/<from_>/<code>")
async def avatar(from_, code):
    try:
        etag = request.headers["if-none-match"]
    except KeyError:
        etag = None

    address = base64.urlsafe_b64decode(repad(from_)).decode("utf-8")
    info = await client.get_avatar(address, metadata_only=True)
    bin_hash = binascii.a2b_hex(info["sha1"])
    new_etag = base64.urlsafe_b64encode(bin_hash).decode("ascii").rstrip("=")

    cache_ttl = timedelta(seconds=current_app.config.get(
        "AVATAR_CACHE_TTL",
        300,
    ))

    response = Response(None, mimetype=info["type"])
    response.headers["etag"] = new_etag
    # XXX: It seems to me that quart expects localtime(?!) in this field...
    response.expires = datetime.now() + cache_ttl
    response.headers["Content-Security-Policy"] = \
        "frame-ancestors 'none'; default-src 'none'; style-src 'unsafe-inline'"

    if etag is not None and new_etag == etag:
        response.status_code = 304
        response.set_data("")
        return response

    data = await client.get_avatar_data(address, info["sha1"])
    response.status_code = 200

    if request.method == "HEAD":
        response.content_length = len(data)
        response.set_data("")
        return response

    response.set_data(data)
    return response


@app.context_processor
def proc():
    def url_for_avatar(entity, hash_, **kwargs):
        return url_for(
            "avatar",
            from_=base64.urlsafe_b64encode(entity.encode("utf-8")).decode("ascii").rstrip("="),
            code=base64.urlsafe_b64encode(binascii.a2b_hex(hash_)[:8]).decode("ascii").rstrip("="),
            **kwargs
        )

    return {
        "url_for_avatar": url_for_avatar,
        "text_to_css": colour.text_to_css,
        "lang": selected_locale(),
    }


app.template_filter("repr")(repr)


from .user import user_bp  # NOQA
app.register_blueprint(user_bp)
