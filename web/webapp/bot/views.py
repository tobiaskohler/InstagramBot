from flask import render_template, request, Blueprint, url_for, session, redirect, flash, jsonify
from flask_login import current_user,login_required
from webapp.bot.forms import TargetsLaden, StartWorkflow, NewBlacklistEntry
from webapp.models import Abonnenten,Abonniert,Source,Statistiken,Targets_done,Targets_raw,Blacklist,Counter,Historical_follower,Tasks,Taskstatus
from webapp import db, app
import tasks
from bot.main import date, timestamp, InstagramBot
from sqlalchemy import func, and_, desc
from celery.task.control import revoke
from celery.result import AsyncResult
from celery.task.control import inspect
import requests, json

import logging

bot = Blueprint('bot', __name__)


@bot.route('/bot', methods=['GET', 'POST'])
@login_required
def index():

    formTargetsLaden = TargetsLaden()
    formStartWorkflow = StartWorkflow()
    form = {'TargetsLaden': formTargetsLaden,
            'StartWorkflow': formStartWorkflow}
    
    global task

    #GET_TARGETS
    targets_raw = Targets_raw.query.all()

    if formTargetsLaden.submit.data and formTargetsLaden.validate_on_submit():

        username_from_formTargetsLaden = form['TargetsLaden'].username.data
        password_from_formTargetsLaden = form['TargetsLaden'].password.data
        url_from_formTargetsLaden = form['TargetsLaden'].zielurl.data

        #Celery-Task, siehe tasks.py
        logging.debug("Task GET_TARGETS gestartet")
        task = tasks.NeueTargetsLaden.delay(username_from_formTargetsLaden, password_from_formTargetsLaden, url_from_formTargetsLaden)

        task_id = task.id
        task_type = "GET_TARGETS"
        task_id_to_db = Tasks(task_id, task_type)
        db.session.add(task_id_to_db)
        db.session.commit()

        return redirect(url_for("bot.output"))

    #WORKFLOW
    if formStartWorkflow.submit2.data and formStartWorkflow.validate_on_submit():

        username_from_formStartWorkflow = form['StartWorkflow'].username.data
        password_from_formStartWorkflow = form['StartWorkflow'].password.data

        #Celery-Task, siehe tasks.py
        logging.debug("Task START_WORKFLOW gestartet")
        task = tasks.WorkflowStarten.delay(username_from_formStartWorkflow, password_from_formStartWorkflow)

        return redirect(url_for("bot.output"))

    return render_template('bot.html', form=form, targets_raw=targets_raw)


@bot.context_processor
def context_processor():

    i = tasks.celery.control.inspect()
    activetasks = i.active()

    if not activetasks:
        task_existence=0
        return dict(task_existence=task_existence)

    else:
        task_existence=1
        return dict(task_existence=task_existence)


@bot.route('/report', methods=['GET', 'POST'])
@login_required
def report():

    #statistik gesamt
    datum = date
    anzahlAbonnenten = Abonnenten.query.count()
    anzahlAbonniert = Abonniert.query.count()
    ratioAbonnentenAbonniert = round(anzahlAbonnenten/anzahlAbonniert*100, 2)
    anzahlLikesTotal = db.session.query(db.func.sum(Counter.like_counter)).scalar()
    anzahlFollowsTotal = db.session.query(db.func.sum(Counter.follow_counter)).scalar()
    ratioLikesFollows = round(anzahlLikesTotal/anzahlFollowsTotal*100, 2)
    anzahlTargetsTotal = Targets_done.query.count()
    anzahlMatches = db.session.query(Targets_done).filter(Targets_done.match=="ja").count()
    ratioTargetsTotalToMatches = round(anzahlMatches/anzahlTargetsTotal*100, 2)
    anzahlTargetsTotalPrivate = db.session.query(Targets_done).filter(Targets_done.followed>0).count()
    anzahlTargetsTotalPublic = db.session.query(Targets_done).filter(Targets_done.pics_liked>=0).count()
    ratioPrivateToMatch = round(anzahlTargetsTotalPrivate/anzahlMatches*100, 2) 
    ratioPublicToMatch = round(anzahlTargetsTotalPublic/anzahlMatches*100, 2)
    anzahlFollowedBack = db.session.query(Targets_done).filter(Targets_done.followed_back>0).count()
    ratioFollowedBack = round(anzahlFollowedBack/anzahlMatches*100,2)
    anzahlLikersFollowedBack = Targets_done.query.filter(and_(Targets_done.match=="ja", Targets_done.pics_liked>=0, Targets_done.followed_back>=0)).count()
    anzahlFollowersFollowedBack = Targets_done.query.filter(and_(Targets_done.match=="ja", Targets_done.pics_liked==None, Targets_done.followed_back>=0)).count()
    ratioLikersFollowedBack = round(anzahlLikersFollowedBack/max(anzahlLikesTotal,0.01)*100,2)
    ratioFollowersFollowedBack = round(anzahlFollowersFollowedBack/max(anzahlFollowsTotal,0.01)*100,2)

    #statistik pro source
    source_ids = Source.query.all()
    source_ids_dict = dict()
    
    source_ids_statistics_dict = dict()

    for elem in source_ids:
        source_ids_dict[elem.id] = elem.source_url

    for key, value in sorted(source_ids_dict.items(), reverse=True):

        total_per_source = Targets_done.query.filter_by(source_id=key).count()
        total_per_source_davon_matches = Targets_done.query.filter_by(source_id=key, match="ja").count()
        total_per_source_davon_likes = Targets_done.query.filter(and_(Targets_done.source_id==key, Targets_done.match=="ja", Targets_done.pics_liked>=0)).count()
        total_per_source_davon_follows = Targets_done.query.filter(and_(Targets_done.source_id==key, Targets_done.match=="ja", Targets_done.pics_liked==None)).count()
        total_per_source_followed_back = Targets_done.query.filter(and_(Targets_done.source_id==key, Targets_done.followed_back>=0)).count()
        total_per_source_like_ratio = round(total_per_source_davon_likes/max(total_per_source_davon_matches, 0.01)*100,2)
        total_per_source_follow_ratio = round(total_per_source_davon_follows/max(total_per_source_davon_matches, 0.01)*100,2)
        total_per_source_followed_back_ratio = round(total_per_source_followed_back/max(total_per_source_davon_matches, 0.01)*100,2)
        total_per_source_match_ratio = round(total_per_source_davon_matches/max(total_per_source, 0.01)*100,2)
        total_per_source_likers_followed_back = Targets_done.query.filter(and_(Targets_done.source_id==key, Targets_done.followed_back>=0, Targets_done.pics_liked>=0)).count()
        total_per_source_followers_followed_back = Targets_done.query.filter(and_(Targets_done.source_id==key, Targets_done.followed_back>=0, Targets_done.pics_liked==None)).count()
        total_per_source_likers_followed_back_ratio = round(total_per_source_likers_followed_back/max(total_per_source_davon_likes,0.01)*100,2)
        total_per_source_followers_followed_back_ratio = round(total_per_source_followers_followed_back/max(total_per_source_davon_follows,0.01)*100,2)

        source_ids_statistics_dict[key] = {"url": value, "total": total_per_source, "matches": total_per_source_davon_matches,
                                            "likes": total_per_source_davon_likes, "follows": total_per_source_davon_follows,
                                            "followed_back": total_per_source_followed_back, "like_ratio":total_per_source_like_ratio,
                                            "follow_ratio": total_per_source_follow_ratio, "followed_back_ratio": total_per_source_followed_back_ratio,
                                            "match-ratio": total_per_source_match_ratio, "likers_followed_back": total_per_source_likers_followed_back,
                                            "followers_followed_back": total_per_source_followers_followed_back, "likers_followed_back_ratio":total_per_source_likers_followed_back_ratio,
                                            "followers_followed_back_ratio":total_per_source_followers_followed_back_ratio}

        #verräter-url

        historical_follower_dict = dict()
        historical_follower_db = Historical_follower.query.all()

        for historical_follower in historical_follower_db:
            historical_follower_dict[historical_follower.target_url]= historical_follower.datum
        
       
    return render_template('report.html', datum=datum, anzahlAbonnenten=anzahlAbonnenten, anzahlAbonniert=anzahlAbonniert,
                            anzahlLikesTotal=anzahlLikesTotal, anzahlFollowsTotal=anzahlFollowsTotal, ratioAbonnentenAbonniert=ratioAbonnentenAbonniert,
                            ratioLikesFollows=ratioLikesFollows, anzahlTargetsTotal=anzahlTargetsTotal, anzahlTargetsTotalPrivate=anzahlTargetsTotalPrivate,
                            anzahlTargetsTotalPublic=anzahlTargetsTotalPublic, anzahlMatches=anzahlMatches, ratioTargetsTotalToMatches=ratioTargetsTotalToMatches,
                            ratioPrivateToMatch=ratioPrivateToMatch, ratioPublicToMatch=ratioPublicToMatch, anzahlFollowedBack=anzahlFollowedBack,
                            ratioFollowedBack=ratioFollowedBack, anzahlLikersFollowedBack=anzahlLikersFollowedBack,
                            anzahlFollowersFollowedBack=anzahlFollowersFollowedBack, ratioLikersFollowedBack=ratioLikersFollowedBack,
                            ratioFollowersFollowedBack=ratioFollowersFollowedBack, source_ids_statistics_dict=source_ids_statistics_dict,
                            historical_follower_dict=historical_follower_dict)


@bot.route('/blacklist', methods=['GET', 'POST'])
@login_required
def blacklist():

    formNewBlacklistEntries = NewBlacklistEntry()

    if formNewBlacklistEntries.validate_on_submit():
        url_from_formNewBlacklistEntries = formNewBlacklistEntries.url.data
        
        add_blacklist_entry = Blacklist(url_from_formNewBlacklistEntries)
        db.session.add(add_blacklist_entry)
        db.session.commit()

        flash(f"'{url_from_formNewBlacklistEntries}' auf Blacklist gesetzt!", category='success')

    
    datum = date

    blacklist_all = Blacklist.query.all()

    return render_template('blacklist.html', formNewBlacklistEntries=formNewBlacklistEntries, datum=datum, blacklist_all=blacklist_all)


@bot.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    delete_blacklist_entry = Blacklist.query.get_or_404(id)
    db.session.delete(delete_blacklist_entry)
    db.session.commit()
    flash(f"'{delete_blacklist_entry.url}' von Blacklist gelöscht!", category='danger')

    return redirect(url_for('bot.blacklist'))


@bot.route('/output', methods=['GET', 'POST'])
@login_required
def output():

    i = tasks.celery.control.inspect()
    activetasks = i.active()
    scheduledtasks = i.scheduled()
    reservedtasks = i.reserved()

    for key in activetasks.keys():

        if "celery@" in key:
            host_id = key

    list_of_tasks = {'activetasks': activetasks, 'scheduledtasks': scheduledtasks, 'reservedtasks': reservedtasks}
    task_id = "no active Task"


    if not activetasks:
        return render_template('output.html', date=date, timestamp=timestamp, task_id=task_id)

    else:
        try:
            task_id = list_of_tasks['activetasks'][host_id][0]['id']   #muss im webserver angepasst werden
            task_type = list_of_tasks['activetasks'][host_id][0]['type']

            if task_type == "tasks.WorkflowStarten":
                running_task = tasks.WorkflowStarten.AsyncResult(task_id)

            elif task_type == "tasks.CheckLists":
                running_task = tasks.CheckLists.AsyncResult(task_id)
                
            else:
                running_task = tasks.NeueTargetsLaden.AsyncResult(task_id)

            state = running_task.state
            time_started = Tasks.query.filter_by(task_id=task_id).first().timestamp
            total_targets_today = Taskstatus.query.filter(Taskstatus.match=="ja").count()
            total_follows_today = Taskstatus.query.filter(Taskstatus.followed!=None).count()
            total_likes_today = db.session.query(db.func.sum(Taskstatus.pics_liked)).scalar()
            total_unfollows_today = Taskstatus.query.filter(Taskstatus.unfollowed!=None).count()

            return render_template('output.html', date=date, timestamp=timestamp, task_id=task_id, state=state, time_started=time_started,
                                    total_targets_today=total_targets_today, total_follows_today=total_follows_today, total_likes_today=total_likes_today,
                                    total_unfollows_today=total_unfollows_today)

        except Exception:
            return render_template('output.html', date=date, timestamp=timestamp, task_id=task_id)


@bot.route('/stop', methods=['GET', 'POST'])
@login_required
def stop():
    #get youngest task_id (currently running)

    #get list of all tasks and look if one task is active or not
    i = tasks.celery.control.inspect()
    activetasks = i.active()
    scheduledtasks = i.scheduled()
    reservedtasks = i.reserved()
    list_of_tasks = {'activetasks': activetasks, 'scheduledtasks': scheduledtasks, 'reservedtasks': reservedtasks}

    for key in activetasks.keys():

        if "celery@" in key:
            host_id = key


    if not activetasks:
        print("NO active tasks running")

    else:
        task_id = list_of_tasks['activetasks'][host_id][0]['id']   #muss im webserver angepasst werden
        print(f"Aktuelle task_id {task_id}")

        tasks.celery.control.revoke(task_id, terminate=True)
        print(f"Task {task_id} got killed!")    #geht nur mit PREFORK unter LINUX (EVENTLET UNTERSTÜZT REVOKE NICHT)

    return redirect(url_for("bot.output"))
