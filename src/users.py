"""Classes related to user management"""

from flask_login import UserMixin
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField


class LoginForm(FlaskForm):
    username = StringField("Username")
    password = PasswordField("Password")
    submit = SubmitField("Submit")


class TheUser(UserMixin):
    """Singleton user used for basic authentication.

    Username and password should be set via environment."""

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def get_id(self):
        return self.username
