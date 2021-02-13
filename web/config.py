import os

class Config(object):
    '''MariaDB-URI: mysql://username:password@db/webapp'''

    base = 'mysql://'
    user = "USERNAME"
    password = "PASSWORD"
    host = "db"
    database = "webapp"
   
    #SQLALCHEMY
    SQLALCHEMY_DATABASE_URI = base + user + ':' + password + '@' + host + '/' + database
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    #FLask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mysecret'
    USR_INSTAGRAM='INSTAGRAM_USERNAME'
    PWD_INSTAGRAM='INSTAGRAM_PASSWORD'
