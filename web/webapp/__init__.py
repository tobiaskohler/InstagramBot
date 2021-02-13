from flask import Flask
from config import Config

####################################################
########Flask INSTANZ###############################

app = Flask(__name__)
app.config.from_object(Config)

####################################################
########SQLAlchemy INSTANZ##########################

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy(app)
Migrate(app, db)

####################################################
########Login Manager INSTANZ#######################

from flask_login import LoginManager

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'users.login'

####################################################
####Blueprints REGISTRIERUNG########################

from webapp.bot.views import bot
from webapp.users.views import users

app.register_blueprint(bot)
app.register_blueprint(users)