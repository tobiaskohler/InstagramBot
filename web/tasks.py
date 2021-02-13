
from webapp import app, db
from celery import Celery
from celery.schedules import crontab    #periodic tasks
from celery.task.control import inspect
from bot.main import InstagramBot
from webapp.models import Abonnenten,Abonniert,Source,Statistiken,Targets_done,Targets_raw,Counter,Tasks,Taskstatus
import datetime
import time

#Celery
rabbitmq_broker_url = 'amqp://'
rabbitmq_result_backend = 'rpc://'
rabbitmq_user = 'RABBITMQ_USERNAME'
rabbitmq_password = 'RABBITMQ_PASSWORD'
rabbitmq_host = 'rabbitmq'          #####IMPORTANT!! NAME OF THE DOCKER-COMPOSE INTERNAL SERVICE!!!!
rabbitmq_venv = 'webapp'
CELERY_BROKER_URL='amqp://user123:password123@rabbitmq//webapp'
CELERY_RESULT_BACKEND='rpc://user123:password123@rabbitmq//webapp'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True


celery = Celery(app.name, broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND, enable_utc=CELERY_ENABLE_UTC, timezone=CELERY_TIMEZONE)


###################################################
####### T A S K   S C H E D U L E #################
#######zeit in UTC, geht nicht anders 

# ClearTaskstatus: jeden Tag vor Check_Lists + Postprocessing
@celery.on_after_configure.connect
def setup_periodic_task(sender, **kwargs):
    sender.add_periodic_task(crontab(minute=1, hour=1), ClearTaskstatus.s())

# Check_lists + Postprocessing + load_all_data: jeden Tag ab 03:00 morgens
@celery.on_after_configure.connect
def setup_periodic_task_periodic(sender, **kwargs):
    sender.add_periodic_task(crontab(minute=2, hour=1), CheckLists.s(app.config['USR_INSTAGRAM'], app.config['PWD_INSTAGRAM']))

# Workflow: jeden Tag ab 07:05 morgens
@celery.on_after_configure.connect
def setup_periodic_task_morning(sender, **kwargs):
    sender.add_periodic_task(crontab(minute=5, hour=5), WorkflowStarten.s(app.config['USR_INSTAGRAM'], app.config['PWD_INSTAGRAM']))

@celery.on_after_configure.connect
def setup_ContinuousTask(sender, **kwargs):
    sender.add_periodic_task(crontab(minute='*/1'), ContinuousTask.s())


####################################################
########T A S K S ##################################

@celery.task(name='ContinuousTask', bind=True)
def ContinuousTask(self):
    heartbeat_value = 30
    for i in range(heartbeat_value):
        time.sleep(1)
    
    anzahlAbonnenten = Abonnenten.query.count()
    heartbeat_return = f"<3_H_E_A_R_T_B_E_A_T_3> MBRKR + MRDB ({anzahlAbonnenten})"

    return heartbeat_return

@celery.task(name='CheckLists', bind=True)
def CheckLists(self, username_from_formTargetsLaden, password_from_formTargetsLaden):
    #get task_id von setup_periodic_task_night
    i = celery.control.inspect()
    activetasks = i.active()
    print(activetasks)

    for key in activetasks.keys():

            if "celery@" in key:
                host_id = key

    print(f"HOST ID ist {host_id}")

    list_of_tasks = {'activetasks': activetasks}          
    task_id = list_of_tasks['activetasks'][host_id][0]['id']   #muss im webserver angepasst werden

    print(f"Aktuelle task_id {task_id}")

    task_type = "CHECK_LISTS"
    task_id_to_db = Tasks(task_id, task_type)
    db.session.add(task_id_to_db)
    db.session.commit()

    instagrambot = InstagramBot(username_from_formTargetsLaden, password_from_formTargetsLaden)
    instagrambot.login()
    load_all_data = instagrambot.load_all_data()        #periodic
    check_lists = instagrambot.check_lists()            #periodic     
    postprocessing = instagrambot.postprocessing()      #periodic 

    return {'load_all_data_protocol': load_all_data, 'check_lists_protocol': check_lists, 'postprocessing_protocol': postprocessing}

@celery.task(name='NeueTargetsLaden', bind=True)
def NeueTargetsLaden(self, username_from_formTargetsLaden, password_from_formTargetsLaden, url_from_formTargetsLaden):
    instagrambot = InstagramBot(username_from_formTargetsLaden, password_from_formTargetsLaden)
    instagrambot.login()
    get_targets = instagrambot.get_targets(url_from_formTargetsLaden)

    return {'get_targets_protocol': get_targets}

@celery.task(name='WorkflowStarten', bind=True)
def WorkflowStarten(self, username_from_formStartWorkflow, password_from_formStartWorkflow):
    i = celery.control.inspect()
    activetasks = i.active()
    print(activetasks)

    for key in activetasks.keys():

            if "celery@" in key:
                host_id = key

    print(f"HOST ID ist {host_id}")

    list_of_tasks = {'activetasks': activetasks}
    task_id = list_of_tasks['activetasks'][host_id][0]['id']   #muss im webserver angepasst werden
    task_type = "WORKFLOW"
    task_id_to_db = Tasks(task_id, task_type)
    db.session.add(task_id_to_db)
    db.session.commit()

    instagrambot = InstagramBot(username_from_formStartWorkflow, password_from_formStartWorkflow)
    instagrambot.login()

    targets_raw_all = Targets_raw.query.with_entities(Targets_raw.target_url)
    targets_raw_all_list = list()

    for elem in targets_raw_all:
        targets_raw_all_list.append(elem[0])

    follow_threshold = 350
    like_threshold = 1.5 * follow_threshold
 
    target_counter = 0

    heute = datetime.datetime.now().date()

    counter_today_query = Counter.query.filter_by(datum=heute).scalar()

#braucht man nicht mehr
    if counter_today_query is None:
        counter_today_query = Counter()
        db.session.add(counter_today_query)
        counter_today_query.follow_counter = 0
        counter_today_query.like_counter = 0
        db.session.commit()

        follow_counter = 0
        like_counter = 0
    
    else:
        total_targets_today = Taskstatus.query.filter(Taskstatus.match=="ja").count()
        total_follows_today = Taskstatus.query.filter(Taskstatus.followed!=None).count()
        total_likes_today = db.session.query(db.func.sum(Taskstatus.pics_liked)).scalar()
        total_unfollows_today = Taskstatus.query.filter(Taskstatus.unfollowed!=None).count()

        if total_targets_today is None:
            total_targets_today = 1
        
        if total_follows_today is None:
            total_follows_today = 1

        if total_likes_today is None:
            total_likes_today = 1
        
        if total_unfollows_today is None:
            total_unfollows_today = 1

        print(f"Bisherige Auslastung Likes: {int(total_likes_today)} ({int(total_likes_today)/int(like_threshold)*100} %)")
        print(f"Bisherige Auslastung Follows: {int(total_follows_today)} ({int(total_follows_today)/int(follow_threshold)*100} %)")

        follow_counter = counter_today_query.like_counter
        print(f"ALTER follow counter {follow_counter}")
        like_counter = counter_today_query.follow_counter
        print(f"ALTER like counter {like_counter}")

    for elem in targets_raw_all_list:

        total_targets_today = Taskstatus.query.filter(Taskstatus.match=="ja").count()
        total_follows_today = Taskstatus.query.filter(Taskstatus.followed!=None).count()
        total_likes_today = db.session.query(db.func.sum(Taskstatus.pics_liked)).scalar()
        total_unfollows_today = Taskstatus.query.filter(Taskstatus.unfollowed!=None).count()

        targets_raw_count = Targets_raw.query.with_entities(Targets_raw.target_url).count()

        if total_targets_today is None:
            total_targets_today = 1
        
        if total_follows_today is None:
            total_follows_today = 1

        if total_likes_today is None:
            total_likes_today = 1
        
        if total_unfollows_today is None:
            total_unfollows_today = 1

        if targets_raw_count is None:
            targets_raw_count = 1


        print(f"------------G E H E   Z U: {elem}------------")

        like_follow = instagrambot.workflow(elem, like_counter, follow_counter)

        like_counter = like_follow[1]
        follow_counter = like_follow[0]

        counter_today_query.datum = heute
        counter_today_query.like_counter = like_counter
        counter_today_query.follow_counter = follow_counter
        db.session.commit()

        print(f"Likes (total): {total_likes_today} (Auslastung: {int(total_likes_today)/int(like_threshold)*100} %) | Follows (total): {total_follows_today} (Auslastung: {int(total_follows_today)/int(follow_threshold)*100} %)")

        target_counter += 1
        print(f"Auslastung Pool: {total_targets_today} von {targets_raw_count} ({int(total_targets_today)/int(targets_raw_count)*100} %)")
        
        if total_likes_today >= like_threshold:
            print(f"------------M A X I M U M   L I K E S ({total_likes_today} von {like_threshold})  E R R E I C H T------------")
            instagrambot.close_browser()
            break

        elif total_follows_today >= follow_threshold:
            print(f"------------M A X I M U M   F O L L O W S ({total_follows_today} von {follow_threshold})  E R R E I C H T------------")
            instagrambot.close_browser()
            break


    return print(f"WorkflowStarten ist fertig! Likes (total): {total_likes_today}, Follows (total): {total_follows_today}")

@celery.task(name='ClearTaskstatus')
def ClearTaskstatus():
    db.session.query(Taskstatus).delete()
    db.session.commit()
    return "Clear Taskstatus-Tabelle erfolgreich!"
