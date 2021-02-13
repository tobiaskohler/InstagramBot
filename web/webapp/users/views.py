from flask import render_template, request, Blueprint, url_for, session, redirect, flash
from flask_login import login_user, current_user, logout_user, login_required
from webapp.users.forms import LoginForm, RegistrationForm
from webapp.models import Users
from webapp import db
import logging

users = Blueprint('users', __name__)

@users.route('/', methods=['GET', 'POST'])
def login():

    form = LoginForm()

    if form.validate_on_submit():

        user = Users.query.filter_by(username=form.username.data).first()

        if user is not None:                                                    #check ob Eintrag in Datenbank vorhanden

            if user.check_password(form.password.data) and user is not None:    #wenn ja, dann check passwort

                login_user(user)
                logging.debug(f"{user} logged in")
                flash("Login erfolgreich!", category='success')

                next = request.args.get("next")

                if next == None or next[0] == "/":
                    next = url_for("bot.index")

                return redirect(next)

            else:
                flash("Passwort falsch!", category='danger')
                logging.debug(f"Passwort falsch!")


        else:
            flash("So jemand kenne ich hier nicht...", category='danger')
            logging.debug(f"Unautorisierter Zugriff!")
          

    return render_template("login.html", form=form)


@users.route("/logout")
def logout():
    logout_user()
    logging.debug(f"Logout korrekt!")

    return redirect(url_for("users.login"))


@users.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():

        if form.username.data == "adminlinalin":

            user = Users(username=form.username.data, password=form.password.data)    #create Instanz einer USer Klasse

            db.session.add(user)
            db.session.commit()

            flash("Danke für die Registrierung!", category='success')
            return redirect(url_for("users.login"))

        else:
            flash("Sorry, keine Anmeldung mehr möglich!", category='danger')
            logging.debug(f"Unautorisierter Registrierungsversuch")

    return render_template("register.html", form=form)
