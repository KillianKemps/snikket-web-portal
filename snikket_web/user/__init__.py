import quart.flask_patch

from quart import Blueprint, render_template, request, redirect, url_for
import quart.exceptions
from flask_wtf import FlaskForm
from flask_babel import lazy_gettext as _l, _
import wtforms

from snikket_web.prosodyclient import client

user_bp = Blueprint('user', __name__, url_prefix="/user")


@user_bp.context_processor
async def proc():
    return {"user_info": await client.get_user_info()}


class ChangePasswordForm(FlaskForm):
    current_password = wtforms.PasswordField(
        _l("Current password"),
        validators=[wtforms.validators.InputRequired()]
    )

    new_password = wtforms.PasswordField(
        _l("New password"),
        validators=[wtforms.validators.InputRequired()]
    )

    new_password_confirm = wtforms.PasswordField(
        _l("Confirm new password"),
        validators=[wtforms.validators.InputRequired(),
                    wtforms.validators.EqualTo(
                        "new_password",
                        _l("The new passwords must match.")
                    )]
    )


class LogoutForm(FlaskForm):
    pass


class ProfileForm(FlaskForm):
    nickname = wtforms.TextField(
        _l("Display name"),
    )

    avatar = wtforms.FileField(
        _l("Avatar")
    )


@user_bp.route("/")
@client.require_session()
async def index():
    user_info = await client.get_user_info()
    return await render_template("user_home.html", user_info=user_info)


@user_bp.route('/passwd', methods=["GET", "POST"])
@client.require_session()
async def change_pw():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            await client.change_password(
                form.current_password.data,
                form.new_password.data,
            )
        except quart.exceptions.Unauthorized:
            # server refused current password, set an appropriate error
            form.errors.setdefault(form.current_password.name, []).append(
                _("Incorrect password"),
            )
        else:
            return redirect(url_for("user.change_pw"))

    return await render_template("user_passwd.html", form=form)


@user_bp.route("/profile", methods=["GET", "POST"])
@client.require_session()
async def profile():
    form = ProfileForm()
    if request.method != "POST":
        user_info = await client.get_user_info()
        form.nickname.data = user_info.get("nickname", "")

    if form.validate_on_submit():
        user_info = await client.get_user_info()

        file_info = (await request.files).get(form.avatar.name)
        if file_info is not None:
            mimetype = file_info.mimetype
            data = file_info.stream.read()
            if len(data) > 0:
                await client.set_user_avatar(data, mimetype)

        if user_info.get("nickname") != form.nickname.data:
            await client.set_user_nickname(form.nickname.data)
        return redirect(url_for(".profile"))

    return await render_template("user_profile.html", form=form)


@user_bp.route("/logout", methods=["GET", "POST"])
@client.require_session()
async def logout():
    form = LogoutForm()
    if form.validate_on_submit():
        await client.logout()
        return redirect(url_for("home"))

    return await render_template("user_logout.html", form=form)
