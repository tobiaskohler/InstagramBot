from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, SubmitField, PasswordField
from wtforms.validators import DataRequired, EqualTo
from wtforms import ValidationError
from wtforms_alchemy import QuerySelectField

from flask_login import current_user
from webapp.models import Abonnenten,Abonniert,Source,Statistiken,Targets_done,Targets_raw
from webapp import db
from sqlalchemy import func


class TargetsLaden(FlaskForm):
    '''Enter Instagram username into "USERNAME" and corresponding password into "PASSWORD'''

    username = StringField("Instagram-Username", default="USERNAME", validators=[DataRequired()])
    password = PasswordField("Instagram-Passwort", default="PASSWORD", validators=[DataRequired()])
    zielurl = StringField('Zielurl (Form: TargetsLaden)', validators=[DataRequired()])
    submit = SubmitField('Los gehts (Form: TargetsLaden)')

# def target_choice_query():
#     return Source.query.group_by(Source.id).all()


class StartWorkflow(FlaskForm):
    '''Enter Instagram username into "USERNAME" and corresponding password into "PASSWORD'''

    username = StringField("Instagram-Username", default="USERNAME", validators=[DataRequired()])
    password = PasswordField("Instagram-Passwort", default="PASSWORD", validators=[DataRequired()])
    #target = QuerySelectField(query_factory=target_choice_query, allow_blank=False, get_label="source_url", validators=[DataRequired()])
    #laufzeit = IntegerField(label='Laufzeit (in Stunden)', default="4", validators=[DataRequired()])
    submit2 = SubmitField('Los gehts (Form: StartWorkflow)')


class NewBlacklistEntry(FlaskForm):
    url = StringField("Instagram-URL", validators=[DataRequired()])
    submit = SubmitField('Eintragen')
