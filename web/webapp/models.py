from webapp import db, login_manager
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin  # is_authenticated is_loggedin usw...

@login_manager.user_loader     # if user is authenticated, then....
def load_user(user_id):
    return Users.query.get(user_id)


class Users(db.Model, UserMixin):
    __tablename__  = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(500))

    def __init__(self, username, password):
        self.username = username
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"Username: {self.username}"


class Abonnenten(db.Model):
    __tablename__ = 'abonnenten'

    abonnenten_url = db.Column(db.String(100), primary_key=True)
    datum = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, abonnenten_url):
        self.abonnenten_url = abonnenten_url

    def __repr__(self):
        return f"Abonnent: {self.abonnenten_url}"


class Abonniert(db.Model):
    __tablename__ = 'abonniert'

    abonniet_url = db.Column(db.String(100), primary_key=True)
    datum = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, abonniet_url):
        self.abonniet_url = abonniet_url

    def __repr__(self):
        return f"Abonniert: {self.abonniet_url}"


class Source(db.Model):

    __tablename__ = 'source'

    id = db.Column(db.Integer, primary_key=True)
    source_url = db.Column(db.String(100), index=True)
    targets_total = db.Column(db.Integer)
    datum = db.Column(db.DateTime, default=datetime.utcnow)
    targets_raw = db.relationship('Targets_raw', backref='targets_raw_quelle')
    targets_done = db.relationship('Targets_raw', backref='targets_done_quelle')

    def __init__(self, source_url):
        self.source_url = source_url

    def __repr__(self):
        return f"Target-Source: {self.source_url} vom: {self.datum}"


class Targets_raw(db.Model):
    __tablename__ = 'targets_raw'

    id = db.Column(db.Integer, primary_key=True)
    target_url = db.Column(db.String(100), index=True)
    source_id = db.Column(db.Integer, db.ForeignKey('source.id'))

    def __init__(self, target_url, source_id):
        self.target_url = target_url
        self.source_id = source_id

    def __repr__(self):
        return f"Target-Account: {self.target_url} und Source-ID: {self.source_id}"


class Targets_done(db.Model):
    __tablename__ = 'targets_done'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('source.id'))
    target_url = db.Column(db.String(100), index=True)
    target_abonnenten = db.Column(db.Integer)
    target_abonniert = db.Column(db.Integer)
    match = db.Column(db.String(10))
    datum_bearbeitet = db.Column(db.DateTime, default=datetime.utcnow)
    pics_liked = db.Column(db.Integer)
    followed = db.Column(db.DateTime)
    unfollowed = db.Column(db.DateTime)
    followed_back = db.Column(db.DateTime)
    t5_indicator = db.Column(db.String(3))
    t1_indicator = db.Column(db.String(3))
    t5_timestamp = db.Column(db.DateTime)
    t1_timestamp = db.Column(db.DateTime)

    def __init__(self, target_url, target_abonnenten, target_abonniert, source_id):
        self.target_url = target_url
        self.target_abonnenten = target_abonnenten
        self.target_abonniert = target_abonniert
        self.source_id = source_id

    def __repr__(self):
        return f"Target-URL: {self.target_url} bearbeitet am {self.datum_bearbeitet}, Anzahl Abonnenten: {self.target_abonnenten}, Anzahl Abonniert: {self.target_abonniert}"
    

class Statistiken(db.Model):
    __tablename__ = "statistik"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer)
    targets_total = db.Column(db.Integer)
    pics_liked = db.Column(db.Integer)
    followed = db.Column(db.Integer)
    unfollowed = db.Column(db.Integer)
    followed_back = db.Column(db.Integer)

    def __init__(self, source_id, targets_total):
        self.source_id = source_id
        self.targets_total = targets_total


class Counter(db.Model):
    __tablename__ = "counter"

    datum = db.Column(db.DateTime, default=datetime.now().date(), primary_key=True)
    like_counter = db.Column(db.Integer)
    follow_counter = db.Column(db.Integer)


class Blacklist(db.Model):
    __tablename__ = "blacklist"

    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(100))
    datum = db.Column(db.DateTime, default=datetime.now().date())

    def __init__(self, url):
        self.url = url
        

class Historical_follower(db.Model):
    __tablename__ = "historical_follower"

    id = db.Column(db.Integer, primary_key=True)
    target_url = db.Column(db.String(100))
    datum = db.Column(db.DateTime, default=datetime.now().date())

    def __init__(self, target_url):
        self.target_url = target_url


class Tasks(db.Model):
    __tablename__ = "tasks"

    task_id = db.Column(db.String(72), primary_key=True)
    task_type = db.Column(db.String(21))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    taskid = db.relationship('Taskstatus', backref="status")

    def __init__(self, task_id, task_type):
        self.task_id = task_id
        self.task_type = task_type


class Taskstatus(db.Model):
    __tablename__ = "taskstatus"

    id = db.Column(db.Integer, primary_key=True)
    taskid = db.Column(db.String(72), db.ForeignKey('tasks.task_id'))
    target_url = db.Column(db.String(100))
    check0 = db.Column(db.String(100))
    check1 = db.Column(db.String(100))
    check2 = db.Column(db.String(100))
    check3 = db.Column(db.String(100))
    check4 = db.Column(db.String(100))
    check5 = db.Column(db.String(100))
    check6 = db.Column(db.String(100))
    match = db.Column(db.String(4))
    followed = db.Column(db.DateTime)
    unfollowed = db.Column(db.DateTime)
    pics_liked = db.Column(db.Integer)
    t5_timestamp = db.Column(db.DateTime)
    t1_timestamp = db.Column(db.DateTime)


    def __init__(self, target_url):
        self.target_url = target_url
