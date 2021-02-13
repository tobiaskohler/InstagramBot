from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo
from wtforms import ValidationError

from flask_login import current_user
from webapp.models import Users


class LoginForm(FlaskForm):
    username = StringField('Benutzername',validators=[DataRequired()])
    password = PasswordField('Passwort', validators=[DataRequired()])
    submit = SubmitField('Log in')

class RegistrationForm(FlaskForm):
    username = StringField('Benutzername',validators=[DataRequired()])
    password = PasswordField('Passwort',validators=[DataRequired(),EqualTo('pass_confirm',message='Passwörter müssen übereinstimmen!')])
    pass_confirm = PasswordField('Bestätigung Passwort',validators=[DataRequired()])
    submit = SubmitField('Registrieren!')
