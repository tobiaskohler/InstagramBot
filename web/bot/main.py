from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from bot import timer
import datetime
import re
import random
import json
import requests

from webapp.models import Abonnenten,Abonniert,Source,Statistiken,Targets_done,Targets_raw,Blacklist,Historical_follower,Tasks,Taskstatus
from webapp import db
import logging
from sqlalchemy import func, and_



####Globalvariablen Anfang####
date = str(datetime.datetime.now().date())
t5_date = str(datetime.datetime.now().date() + datetime.timedelta(5))
t1_date = str(datetime.datetime.now().date() + datetime.timedelta(1))

dateDelta = str(datetime.datetime.now().date() - datetime.timedelta(7))
timestamp = str(datetime.datetime.now().strftime('%H-%M-%S'))


class InstagramBot:

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.options = Options()
        self.options.headless = True
        self.profile = webdriver.FirefoxProfile()
        self.profile.set_preference('intl.accept_languages', 'de-DE, de')
        self.profile.update_preferences()

        self.firefox_capabilities = DesiredCapabilities.FIREFOX
        self.firefox_capabilities['marionette'] = True

        self.firefox_binary = FirefoxBinary('/usr/local/bin/firefox')

        self.driver = webdriver.Firefox(capabilities=self.firefox_capabilities, firefox_binary=self.firefox_binary, firefox_profile=self.profile, options=self.options, executable_path="/usr/local/bin/geckodriver")
        logging.debug("Instanz erstellt...")
        print("Instanz erstellt...")

    def close_browser(self):
        self.driver.close()


    def login(self):
        
        logging.debug("Open Firefox")
        print("Open Firefox")

        driver = self.driver
        driver.get("https://www.instagram.de/")
        timer.powernap()

        login_button = driver.find_element_by_xpath("//a[@href='/accounts/login/?source=auth_switcher']")
        login_button.click()
        timer.powernap()

        user_name_element = driver.find_element_by_name("username")
        user_name_element.clear()
        user_name_element.send_keys(self.username)

        timer.powernap()

        password_element = driver.find_element_by_name("password")
        password_element.clear()
        password_element.send_keys(self.password)

        timer.powernap()

        password_element.send_keys(Keys.RETURN)

        timer.powernap()

        logging.debug("Login erfolgreich (Datum: " + date + ", Uhrzeit: " + timestamp + ")")
        print("Login erfolgreich (Datum: " + date + ", Uhrzeit: " + timestamp + ")")

    #schreibt alle targetaccounts von source in datenbank
    def get_targets(self, bildurl):

        targetsBild = list()
        has_next_page = True

        driver = self.driver

        logging.debug(f"######## Open {bildurl} ########")
        print(f"######## Open {bildurl} ########")
        driver.get(bildurl)

        timer.kurzschlafen()

        bildurl_shortcode = '"' + bildurl.split("/")[4] + '"'
        print(bildurl_shortcode)

        logging.debug(f"Source ({bildurl}) in Datenbank sichern...")
        print(f"Source ({bildurl}) in Datenbank sichern...")

        source = Source(source_url=str(bildurl))
        db.session.add(source)
        db.session.commit()

        source_query = Source.query.filter_by(source_url=bildurl).first()
        logging.debug(f"Source ID: {source_query.id}")
        print(f"Source ID: {source_query.id}")

        instagram_url = "https://www.instagram.com/"
        base_url = "https://www.instagram.com/graphql/query/?query_hash="
        follower_query_hash = "d5d763b1e2acf209d62d22d184488e57"
        variables = "&variables="
        shortcode = '"shortcode":' + bildurl_shortcode
        include_reel = '"include_reel":true'
        first = '"first":24'

        target_bild_api = base_url + follower_query_hash + variables + "{" + shortcode + ',' + include_reel + ',' + first + '}'

        while has_next_page == True:

            driver.get(target_bild_api)
            print(f"Open: {target_bild_api}")
            logging.debug(f"Open: {target_bild_api}")

            target_bild_json_response = json.loads(driver.find_element_by_tag_name('body').text)

            targets = target_bild_json_response['data']['shortcode_media']['edge_liked_by']['edges']
            targets_total = target_bild_json_response['data']['shortcode_media']['edge_liked_by']['count']

            for target in targets:
                username = target['node']['username']
                target_url = instagram_url + username
                print(f"Erfasse: {target_url}")
                logging.debug(f"Erfasse: {target_url}")
                targetsBild.append(target_url)

            print(f"Fortschritt: {round((len(targetsBild)/targets_total)*100, 2)} %")
            logging.debug(f"Fortschritt: {round((len(targetsBild)/targets_total)*100,2)} %")

            has_next_page = target_bild_json_response['data']['shortcode_media']['edge_liked_by']['page_info']['has_next_page']

            if has_next_page == True:
                end_cursor = '"' + target_bild_json_response['data']['shortcode_media']['edge_liked_by']['page_info']['end_cursor'] + '"'
                print(f"end cursor: {end_cursor}")
                target_bild_api = base_url + follower_query_hash + variables + "{" + shortcode + ',' + include_reel + ',' + first + ',' + '"after":' + end_cursor + '}'

            timer.scrollpause()

        for target in targetsBild:
            target_raw = Targets_raw(target_url=target, source_id=source_query.id)
            db.session.add(target_raw)
            db.session.commit()
            logging.debug(f"added {target_raw} to database")
            print(f"added {target_raw} to database")

        logging.debug("Alle Datenbankeinträge erfolgreich!")
        print("Alle Datenbankeinträge erfolgreich!")

        driver.close()
        print("Browser geschlossen!")
        logging.debug("Browser geschlossen!")

        get_targets_protocol = {'Status': 'get_targets erledigt', 'Target_URL': bildurl, 'TotalTargets': targets_total}

        return get_targets_protocol

    #load_All_data geht die abonniert und abonnnentenliste durch und schreibt neu dazugekommene in die datenbank, wenn targetaccounts sich dazu entschlossen haben nicht mehr zu folgen, dann wird das delta auch in db geschrieben
    def load_all_data(self):                                            #periodischer task

        driver = self.driver

        #Abonnenten
        followers_in_db_before = Abonnenten.query.all()
        abonnentenLina = list()
        has_next_page = True
        historical_followers = list()

        for follower in followers_in_db_before:
            historical_followers.append(follower.abonnenten_url)

        logging.debug("######## Abonnenten ########")
        print("######## Abonnenten ########")

        instagram_url = "https://www.instagram.com/"
        base_url = "https://www.instagram.com/graphql/query/?query_hash="
        follower_query_hash = "c76146de99bb02f6415203be841dd25a"
        variables = "&variables="
        bot_id = '"id":8736970512'
        include_reel = '"include_reel":true'
        fetch_mutual = '"fetch_mutual":true'
        first = '"first":24'

        follower_api_url = base_url + follower_query_hash + variables + "{" + bot_id + ',' + include_reel + ',' + fetch_mutual + ',' + first + '}'
        
        while has_next_page == True:

            driver.get(follower_api_url)
            print(f"Open: {follower_api_url}")
            logging.debug(f"Open: {follower_api_url}")

            follower_json_response = json.loads(driver.find_element_by_tag_name('body').text)

            followers = follower_json_response['data']['user']['edge_followed_by']['edges']
            follower_total = follower_json_response['data']['user']['edge_followed_by']['count']

            for follower in followers:
                username = follower['node']['username']
                target_url = instagram_url + username
                print(f"Erfasse: {target_url}")
                logging.debug(f"Erfasse: {target_url}")
                abonnentenLina.append(target_url)

            print(f"Fortschritt: {round((len(abonnentenLina)/follower_total)*100, 2)} %")
            logging.debug(f"Fortschritt: {round((len(abonnentenLina)/follower_total)*100,2)} %")

            has_next_page = follower_json_response['data']['user']['edge_followed_by']['page_info']['has_next_page']

            if has_next_page == True:
                end_cursor = '"' + follower_json_response['data']['user']['edge_followed_by']['page_info']['end_cursor'] + '"'
                print(f"end cursor: {end_cursor}")
                follower_api_url = base_url + follower_query_hash + variables + "{" + bot_id + ',' + include_reel + ',' + fetch_mutual + ',' + first + ',' + '"after":' + end_cursor + '}'

            timer.scrollpause()

        neuAbonnenten = []

        for item in abonnentenLina:

            db_entry_check = Abonnenten.query.filter_by(abonnenten_url=item).scalar()

            if db_entry_check is None:
                logging.debug(f"Erfolg: {item} neuer Abonnent!")
                print(f"Erfolg: {item} neuer Abonnent!")
                neuAbonnenten.append(item)
                abonnent = Abonnenten(item)
                db.session.add(abonnent)
                db.session.commit()

            else:
                # logging.debug(f"{item} bereits in Datenbank")
                # print(f"{item} bereits in Datenbank")
                pass

        timer.powernap()

        print("Vergleiche, ob Abonnenten verloren")
        logging.debug("Vergleiche, ob Abonnenten verloren")

        for follower in historical_followers:
            if follower not in abonnentenLina:
                print(f"Abonnent verloren: {follower}")
                logging.debug(f"Abonnent verloren: {follower}")
                historical_follower = Historical_follower(follower)
                db.session.add(historical_follower)
                historical_follower = Abonnenten.query.filter_by(abonnenten_url=follower).delete()
                print(f"Lösche {historical_follower}")
                db.session.commit()

        timer.powernap()

        #Abonniert

        abonniertLina = list()
        has_next_page = True

        logging.debug("######## Abonniert ########")
        print("######## Abonniert ########")

        instagram_url = "https://www.instagram.com/"
        base_url = "https://www.instagram.com/graphql/query/?query_hash="
        following_query_hash = "d04b0a864b4b54837c0d870b0e77e076"
        variables = "&variables="
        bot_id = '"id":8736970512'
        include_reel = '"include_reel":true'
        fetch_mutual = '"fetch_mutual":true'
        first = '"first":24'

        following_api_url = base_url + following_query_hash + variables + "{" + bot_id + ',' + include_reel + ',' + fetch_mutual + ',' + first + '}'
        
        while has_next_page == True:

            driver.get(following_api_url)
            print(f"Open: {following_api_url}")
            logging.debug(f"Open: {following_api_url}")

            following_json_response = json.loads(driver.find_element_by_tag_name('body').text)

            followings = following_json_response['data']['user']['edge_follow']['edges']
            followings_total = following_json_response['data']['user']['edge_follow']['count']

            for followee in followings:
                username = followee['node']['username']
                target_url = instagram_url + username
                print(f"Erfasse: {target_url}")
                logging.debug(f"Erfasse: {target_url}")
                abonniertLina.append(target_url)

            print(f"Fortschritt: {round((len(abonniertLina)/followings_total)*100,2)} %")
            logging.debug(f"Fortschritt: {round((len(abonniertLina)/followings_total)*100,2)} %")

            has_next_page = following_json_response['data']['user']['edge_follow']['page_info']['has_next_page']

            if has_next_page == True:
                end_cursor = '"' + following_json_response['data']['user']['edge_follow']['page_info']['end_cursor'] + '"'
                print(f"end cursor: {end_cursor}")
                following_api_url = base_url + following_query_hash + variables + "{" + bot_id + ',' + include_reel + ',' + fetch_mutual + ',' + first + ',' + '"after":' + end_cursor + '}'

            timer.scrollpause()

        neuAbonniert = []

        for item in abonniertLina:

            db_entry_check = Abonniert.query.filter_by(abonniet_url=item).scalar()

            if db_entry_check is None:
                logging.debug(f"Abonniert: {item} erfasst!")
                print(f"Abonniert: {item} erfasst!")
                neuAbonniert.append(item)
                abonniert = Abonniert(item)
                db.session.add(abonniert)
                db.session.commit()

            else:
                # logging.debug(f"{item} bereits in Datenbank")
                # print(f"{item} bereits in Datenbank")
                pass

        timer.powernap()

        driver.close()

        print("Browser geschlossen!")
        logging.debug("Browser geschlossen!")

        load_all_data_protocol = {'Status': 'load_all_data erledigt', 'Datum': date, 'Zeit': timestamp, 'Abonnenten': len(abonnentenLina), 'Abonnenten_neu': len(neuAbonnenten), 'Abonniert': len(abonniertLina), 'Abonniert_neu': len(neuAbonniert)}

        logging.debug({'Status': 'load_all_data erledigt', 'Datum': date, 'Zeit': timestamp, 'Abonnenten': len(abonnentenLina), 'Abonnenten_neu': len(neuAbonnenten), 'Abonniert': len(abonniertLina), 'Abonniert_neu': len(neuAbonniert)})

        return load_all_data_protocol

    #hauptworkflow
    def workflow(self, target_url, like_counter, follow_counter):

        driver = self.driver

        like_counter_inner = 0
        follow_counter_inner = 0

        target_for_taskstatus = Taskstatus(target_url)
        db.session.add(target_for_taskstatus)
        db.session.commit()

        target_for_taskstatus = Taskstatus.query.filter_by(target_url=target_url).first()

        print(f"Check 0: {target_url} - Blacklist?")
        logging.debug(f"Check 0: {target_url} - Blacklist?")

        target_in_blacklist = Blacklist.query.filter_by(url=target_url).first()

        if target_in_blacklist is None:
            print(f"Check 0: passed")
            logging.debug(f"Check 0: passed")

            target_for_taskstatus.check0 = "passed"
            db.session.commit()

            print(f"Check 1: {target_url} - Abonnent?")
            logging.debug(f"Check 1: {target_url} - Abonnent?")

            target_in_abonnenten = Abonnenten.query.filter_by(abonnenten_url=target_url).first()

            if target_in_abonnenten is None:
                print(f"Check 1: passed")
                logging.debug(f"Check 1: passed")

                target_for_taskstatus.check1 = "passed"
                db.session.commit()

                print(f"Check 2: Check ob {target_url} - bearbeitet?")
                logging.debug(f"Check 2: Check ob {target_url} - bearbeitet?")

                target_in_targets_done = Targets_done.query.filter_by(target_url=target_url).scalar()

                if target_in_targets_done is None:
                    print(f"Check 2: passed")
                    logging.debug(f"Check 2: passed")

                    target_for_taskstatus.check2 = "passed"
                    db.session.commit()

                    driver.get(target_url)
                    timer.powernap()

                    print(f"Check 3: {target_url} - Existenz?")
                    logging.debug(f"Check 3: {target_url} - Existenz?")

                    try:
                        errorContainer = driver.find_element_by_xpath("//div[@class='error-container -cx-PRIVATE-ErrorPage__errorContainer -cx-PRIVATE-ErrorPage__errorContainer__']")

                        if errorContainer:
                            global nextsite
                            nextsite = 1

                    except NoSuchElementException:
                        nextsite = 0
                        print(f"Check 3: passed")
                        logging.debug(f"Check 3: passed")

                        target_for_taskstatus.check3 = "passed"
                        db.session.commit()




                        if nextsite == 0:
                            print(f"Check 4: {target_url} - Anzahl Abonnenten?")
                            logging.debug(f"Check 4: {target_url} - Anzahl Abonnenten?")

                            abonnenten = driver.find_elements_by_css_selector("span.g47SY")[1].get_attribute("title")
                            abonniert = driver.find_elements_by_css_selector("span.g47SY")[2].text

                            if not abonnenten:
                                abonnentenBereinigt = 1
                                abonniertBereinigt = 1

                            else:
                                abonnentenBereinigt = int(abonnenten.replace(".", ""))
                                abonniertBereinigt = int(abonniert.replace(".",""))

                            if abonnentenBereinigt == 0:
                                abonnentenBereinigt = 0.01

                            if abonniertBereinigt == 0:
                                abonniertBereinigt = 0.01

                            if abonnentenBereinigt <= 700:

                                print(f"Check 4: passed - {abonnentenBereinigt} Abonnenten | {abonniertBereinigt} Abonnierte")
                                logging.debug(f"Check 4: passed - {abonnentenBereinigt} Abonnenten | {abonniertBereinigt} Abonnierte")

                                target_for_taskstatus.check4 = "passed"
                                db.session.commit()


                                print(f"Check 5: {target_url} - URL?")
                                logging.debug(f"Check 5: {target_url} - URL?")

                                try:
                                    url_in_bio = driver.find_element_by_css_selector("a.yLUwa").text

                                    if url_in_bio:
                                        global url_indicator
                                        url_indicator = 1
                                        print(f"###URL identifiziert: -{url_in_bio}")
                                        logging.debug(f"###URL identifiziert: {target_url} -{url_in_bio}")

                                except NoSuchElementException:
                                    url_indicator = 0
                                    print(f"Check 5: passed")
                                    logging.debug(f"Check 5: passed")

                                    target_for_taskstatus.check5 = "passed"
                                    db.session.commit()

                                if url_indicator == 0:

                                    print(f"Check 6: Check ob {target_url} - Privat/Public?")
                                    logging.debug(f"Check 6: Check ob {target_url} - Privat/Public?")

                                    
                                    try:
                                        checkPublicAccount = driver.find_element_by_css_selector("h2.rkEop").text

                                        if checkPublicAccount:
                                            global public_account
                                            public_account = 0
                                            print(f"Check 6: privat")
                                            logging.debug(f"Check 6: privat")

                                            target_for_taskstatus.check6 = "privat"
                                            db.session.commit()

                                    except NoSuchElementException:
                                            public_account = 1
                                            print(f"Check 6: öffentlich")
                                            logging.debug(f"Check 6: öffentlich")

                                            target_for_taskstatus.check6 = "öffentlich"
                                            db.session.commit()

                                    #Routine für Private Accounts
                                    if public_account == 0:

                                        timer.powernap()

                                        followButton = driver.find_element_by_xpath("//button[@type='button']")
                                        timer.scrollpause()

                                        if followButton.text == "Anfrage gesendet" or followButton.text == "Auch folgen":
                                            print(f"{target_url} bereits Anfrage gesendet bzw. folgt bereits!")
                                            logging.debug(f"{target_url} bereits Anfrage gesendet bzw. folgt bereits!")

                                            target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                                            return follow_counter, like_counter                                           

                                        else:
                                            followButton.click()
                                            print(f"###Followed: {target_url}")
                                            logging.debug(f"###Followed: {target_url}")

                                            follow_counter_inner = 1
                                            follow_counter = follow_counter + follow_counter_inner

                                            source_query = Targets_raw.query.filter_by(target_url=target_url).first()
                                            source_id = source_query.source_id

                                            target_done_gefolgt = Targets_done(target_url, abonnentenBereinigt, abonniertBereinigt, source_id)
                                            db.session.add(target_done_gefolgt)

                                            target_done_gefolgt.match = "ja"
                                            target_done_gefolgt.followed = datetime.datetime.utcnow()

                                            target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                                            target_for_taskstatus.match = "ja"
                                            target_for_taskstatus.followed = datetime.datetime.utcnow()

                                            db.session.commit()

                                            timer.langschlafen()

                                            return follow_counter, like_counter

                                    #Routine für Öffenltiche Accounts
                                    else:

                                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                                        timer.scrollpause()

                                        hrefs = driver.find_elements_by_tag_name("a")

                                        picHrefs = [elem.get_attribute("href") for elem in hrefs]
                                        picHrefsFiltered = []

                                        for url in picHrefs:
                                            if "https://www.instagram.com/p/" in url:
                                                picHrefsFiltered.append(url)

                                        sliceZufall = random.randint(2, 5)

                                        if len(picHrefsFiltered) > 0:#neu indention raus
                                            #anzahl bilder entspricht anzahl zufallsauswahl"

                                            print("###Liken von " + str(sliceZufall) + " Bildern")
                                            picHrefsFilteredSliced = picHrefsFiltered[:sliceZufall]
                                            pic_counter = 0

                                            for pic in picHrefsFilteredSliced:
                                                try:
                                                    driver.get(pic)
                                                    timer.powernap()
                                                    driver.find_element_by_xpath("//span[@class='fr66n']").click()
                                                    print(f"##Liked: {pic}")
                                                    logging.debug(f"##Liked: {pic}")
                                                    pic_counter = pic_counter + 1
                                                    timer.kurzschlafen()

                                                except Exception:
                                                    timer.powernap()

                                            like_counter_inner = pic_counter
                                            like_counter = like_counter + like_counter_inner

                                            source_query = Targets_raw.query.filter_by(target_url=target_url).first()
                                            source_id = source_query.source_id

                                            target_done_geliked = Targets_done(target_url, abonnentenBereinigt, abonniertBereinigt, source_id)
                                            db.session.add(target_done_geliked)
                                            target_done_geliked.match = "ja"
                                            target_done_geliked.pics_liked = pic_counter
                                            target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                                            target_for_taskstatus.match = "ja"
                                            target_for_taskstatus.pics_liked = pic_counter

                                            db.session.commit()

                                            timer.langschlafen()

                                            return follow_counter, like_counter

                                        else: #neu
                                            print(f"Keine Bilder vorhanden -> Folge {target_url}")
                                            logging.debug(f"Keine Bilder vorhanden -> Folge {target_url}")

                                            driver.find_element_by_tag_name('body').send_keys(Keys.CONTROL + Keys.HOME)

                                            try:
                                                followButton = driver.find_element_by_xpath("//button[@type='button']")

                                                timer.scrollpause()

                                                if followButton.text == "Anfrage gesendet" or followButton.text == "Auch folgen":
                                                    print(f"{target_url} bereits Anfrage gesendet bzw. folgt bereits!")
                                                    logging.debug(f"{target_url} bereits Anfrage gesendet bzw. folgt bereits!")

                                                    target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                                                else:
                                                    followButton.click()
                                                    print(f"###Followed: {target_url}")
                                                    logging.debug(f"###Followed: {target_url}")

                                                    follow_counter_inner = 1
                                                    follow_counter = follow_counter + follow_counter_inner

                                                    source_query = Targets_raw.query.filter_by(target_url=target_url).first()
                                                    source_id = source_query.source_id

                                                    target_done_gefolgt = Targets_done(target_url, abonnentenBereinigt, abonniertBereinigt, source_id)
                                                    db.session.add(target_done_gefolgt)
                                                    target_done_gefolgt.match = "ja"
                                                    target_done_gefolgt.followed = datetime.datetime.utcnow()
                                                    target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()
                                                    
                                                    target_for_taskstatus.match = "ja"
                                                    target_for_taskstatus.followed = datetime.datetime.utcnow()

                                                    db.session.commit()

                                                    timer.langschlafen()

                                                    return follow_counter, like_counter




                                            except NoSuchElementException:

                                                try:
                                                    followButton = driver.find_element_by_xpath("//button[@class='_5f5mN       jIbKX  _6VtSN     yZn4P   ']")

                                                    timer.scrollpause()

                                                    if followButton.text == "Anfrage gesendet" or followButton.text == "Auch folgen":
                                                        print(f"{target_url} bereits Anfrage gesendet bzw. folgt bereits!")
                                                        logging.debug(f"{target_url} bereits Anfrage gesendet bzw. folgt bereits!")

                                                        target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                                                    else:
                                                        followButton.click()
                                                        print(f"###Followed: {target_url}")
                                                        logging.debug(f"###Followed: {target_url}")

                                                        follow_counter_inner = 1
                                                        follow_counter = follow_counter + follow_counter_inner

                                                        source_query = Targets_raw.query.filter_by(target_url=target_url).first()
                                                        source_id = source_query.source_id

                                                        target_done_gefolgt = Targets_done(target_url, abonnentenBereinigt, abonniertBereinigt, source_id)
                                                        db.session.add(target_done_gefolgt)
                                                        target_done_gefolgt.match = "ja"
                                                        target_done_gefolgt.followed = datetime.datetime.utcnow()
                                                        target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()
                                                        
                                                        target_for_taskstatus.match = "ja"
                                                        target_for_taskstatus.followed = datetime.datetime.utcnow()

                                                        db.session.commit()

                                                        timer.langschlafen()

                                                        return follow_counter, like_counter






                                                except NoSuchElementException:
                                                    print("Zwecklos")

                                else:
                                    print(f"#########################{target_url} - Check 5 failed, URL in BIO")
                                    logging.debug(f"#########################{target_url} - Check 5 failed, URL in BIO")

                                    target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                                    target_for_taskstatus.check5 = "URL in BIO"

                                    db.session.commit()

                                    return follow_counter, like_counter

                            else:
                                print(f"#########################{target_url} - Check 4 failed, Anzahl Abonnenten {abonnentenBereinigt}")
                                logging.debug(f"#########################{target_url} - Check 4 failed, Anzahl Abonnenten {abonnentenBereinigt}")
                                
                                source_query = Targets_raw.query.filter_by(target_url=target_url).first()
                                source_id = source_query.source_id

                                target_url_anzahl_abonnent = Targets_done(target_url, abonnentenBereinigt, abonniertBereinigt, source_id)
                                db.session.add(target_url_anzahl_abonnent)
                                target_url_anzahl_abonnent_match = Targets_done.query.filter_by(target_url=target_url).first()
                                target_url_anzahl_abonnent_match.match = "no"

                                target_for_taskstatus.check4 = "AnzahlAbonnenten_AnzahlAbonniert"

                                db.session.commit()

                                target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()
                                db.session.commit()

                                return follow_counter, like_counter

                    else:
                        print(f"#########################{target_url} - Check 3 failed, nicht mehr existent")
                        logging.debug(f"#########################{target_url} - Check 3 failed, nicht mehr existent")

                        target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                        target_for_taskstatus.check3 = "nicht mehr existent"

                        db.session.commit()

                        return follow_counter, like_counter

                else:
                    print(f"#########################{target_url} - Check 2 failed, bereits bearbeitet")
                    logging.debug(f"#########################{target_url} - Check 2 failed, bereits bearbeitet")

                    target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                    target_for_taskstatus.check2 = "bereits bearbeitet"

                    db.session.commit()
                    return follow_counter, like_counter

            else:
                print(f"#########################{target_url} - Check 1 failed, bereits in Abonnenten")
                logging.debug(f"#########################{target_url} - Check 1 failed, bereits in Abonnenten")

                target_raw_bereits_abonnent = Targets_raw.query.filter_by(target_url=target_url).delete()

                target_for_taskstatus.check1 = "bereits in Abonnenten"

                db.session.commit()
                return follow_counter, like_counter

        else:
            print(f"#########################{target_url} - Check 0 failed, Blacklisteintrag!")
            logging.debug(f"#########################{target_url} - Check 0 failed, Blacklisteintrag!")

            target_raw_blacklist = Targets_raw.query.filter_by(target_url=target_url).delete()

            target_for_taskstatus.check0 = "Blacklisteintrag"

            db.session.commit()
            return follow_counter, like_counter

        driver.close()

        workflow_starten_protocol = {"status": "WorkflowStarten erledigt", "likes": like_counter, "follows": follow_counter}
        return workflow_starten_protocol

    #check_list gleicht ab, ob der target account nun in entweder abonnentenliste oder abonniertliste ist
    def check_lists(self):                                     #periodischer task 
        
        t5list = list()
        t1list = list()
        new_abo = list()

        matches_done_total = Targets_done.query.filter_by(match="ja")
        matches_done_total_list = list()

        for entry in matches_done_total:
            matches_done_total_list.append(entry.target_url)

        print(f"Anzahl Matches in DB: {len(matches_done_total_list)}")

        abonnenten_total = Abonnenten.query.all()
        abonnenten_total_list = list()

        for entry in abonnenten_total:
            abonnenten_total_list.append(entry.abonnenten_url)

        print(f"Anzahl Abonnenten in DB: {len(abonnenten_total_list)}")
  
        abonniert_total = Abonniert.query.all()
        abonniert_total_list = list()

        for entry in abonniert_total:
            abonniert_total_list.append(entry.abonniet_url)

        print(f"Anzahl Abonniert in DB: {len(abonniert_total_list)}")

        for match_done in matches_done_total_list:

            if match_done in abonnenten_total_list and match_done in abonniert_total_list:

                check_entry = Targets_done.query.filter_by(target_url=match_done).first()
                check_t1 = check_entry.t1_indicator

                if check_t1=="yes" and check_entry.followed_back==None:
                    print(f"Erfolg, jetzt Abonnent: {match_done} ({date}), kam aus t1 Nachbearbeitung")
                    logging.debug(f"Erfolg, jetzt Abonnent: {match_done} ({date}), kam aus t1 Nachbearbeitung")

                    match_done_t1 = Targets_done.query.filter_by(target_url=match_done).first()
                    match_done_t1.followed_back = date
                    db.session.commit()

                elif check_entry.followed_back!=None:
                    # print(f"{match_done} bereits abgeglichen!")
                    # logging.debug(f"{match_done} bereits abgeglichen!")
                    pass

                else:
                    print(f"Erfolg, jetzt Abonnent: {match_done} ({date}) + t5 Indikator gesetzt")
                    logging.debug(f"Erfolg, jetzt Abonnent: {match_done} ({date}) + t5 Indikator gesetzt")

                    match_done_t5 = Targets_done.query.filter_by(target_url=match_done).first()
                    match_done_t5.followed_back = date
                    match_done_t5.t5_indicator = "yes"
                    match_done_t5.t1_indicator = "no"
                    match_done_t5.t5_timestamp = t5_date
                    db.session.commit()

                    t5list.append(match_done)

            elif match_done in abonnenten_total_list:

                check_entry = Targets_done.query.filter_by(target_url=match_done).first()
                check_t1 = check_entry.t1_indicator

                if check_t1=="yes" and check_entry.followed_back==None:
                    print(f"Erfolg, jetzt Abonnent: {match_done} ({date}), kam aus t1 Nachbearbeitung")
                    logging.debug(f"Erfolg, jetzt Abonnent: {match_done} ({date}), kam aus t1 Nachbearbeitung")

                    match_done_t1 = Targets_done.query.filter_by(target_url=match_done).first()
                    match_done_t1.followed_back = date
                    db.session.commit()

                elif check_entry.followed_back!=None:
                    # print(f"{match_done} bereits abgeglichen!")
                    # logging.debug(f"{match_done} bereits abgeglichen!")
                    pass

                else:
                    print(f"Erfolg, jetzt Abonnent: {match_done} ({date})")
                    logging.debug(f"Erfolg, jetzt Abonnent: {match_done} ({date})")

                    match_done_success = Targets_done.query.filter_by(target_url=match_done).first()
                    match_done_success.followed_back = date
                    db.session.commit()

                    new_abo.append(match_done)

            elif match_done in abonniert_total_list:
                check_entry = Targets_done.query.filter_by(target_url=match_done).first()
                check_t1 = check_entry.t1_indicator

                # if check_t1=="yes" and check_entry.followed_back!=None:
                #     print(f"Erfolg, jetzt Abonnent: {match_done} ({date}), kam aus t1 Nachbearbeitung")
                #     logging.debug(f"Erfolg, jetzt Abonnent: {match_done} ({date}),  kam aus t1 Nachbearbeitung")

                #     match_done_t1 = Targets_done.query.filter_by(target_url=match_done).first()
                #     match_done_t1.followed_back = date
                #     db.session.commit()

                if check_t1!=None:
                    # print(f"{match_done} bereits abgeglichen!")
                    # logging.debug(f"{match_done} bereits abgeglichen!")
                    pass

                else:
                    print(f"{match_done} in Abonniertliste + t1 Indikator gesetzt")
                    logging.debug(f"{match_done} in Abonniertliste + t1 Indikator gesetzt")

                    match_done_t1 = Targets_done.query.filter_by(target_url=match_done).first()
                    match_done_t1.t1_indicator = "yes"
                    match_done_t1.t5_indicator = "no"
                    match_done_t1.t1_timestamp = t1_date
                    db.session.commit()

                    t1list.append(match_done)

            else:
                # print(f"{match_done} weder in Abonniert noch in Abonneten")
                pass

        timer.powernap()

        check_lists_protocol = {'Status': 'check_lists erledigt', 't5_indicator': len(t5list), 't1_indicator': len(t1list), 'neueAbonnenten':len(new_abo)}

        logging.debug(f"Job erfolgreich: T5-Indikator gesetzt: {len(t5list)} | T1-Indikator gesetzt {len(t1list)} | neue Abonnenten: {len(new_abo)}")
        return check_lists_protocol

                #aufpassen! Wenn hier einträge nach 30 Tagen gelöscht werden, verschwinden sie für die prüfung.
                # mitunter kann es so passieren, dass targets irgendwann in die abonniertliste kommen, denen man nicht 
                # mehr entfolgt. warum? Weil der check nicht mehr gefahren wird, weil nach 30 tagen das target entfernt wurde!

    #nachbearbeitung aller account mit t5 (unfollow) und t1 (like/unfollow) indikatoren
    def postprocessing(self):

        t5list = list()

        t5_db = Targets_done.query.filter(and_(Targets_done.t5_indicator=="yes", Targets_done.t5_timestamp<date, Targets_done.unfollowed==None)).all()

        for t5 in t5_db:
            t5list.append(t5.target_url)
        print(f"Anzahl t5-Timestamp Accounts: {len(t5list)}")
        logging.debug(f"Anzahl t5-Anzahl Timestamp Accounts: {len(t5list)}")

        print(f"Checke Accounts mit t5-Timestamp")
        logging.debug(f"Checke Accounts mit t5-Timestamp")

        driver = self.driver

        for to_unfollow in t5list:

            target_for_taskstatus = Taskstatus(to_unfollow)
            db.session.add(target_for_taskstatus)
            db.session.commit()

            target_for_taskstatus = Taskstatus.query.filter_by(target_url=to_unfollow).first()

            to_unfollow_db = Targets_done.query.filter_by(target_url=to_unfollow).first()

            timer.powernap()

            driver.get(to_unfollow)

            timer.powernap()

            print(f"Check 1: Check ob {to_unfollow} noch existent?")
            logging.debug(f"Check 1: Check ob {to_unfollow} noch existent?")

            try:
                errorContainer = driver.find_element_by_xpath("//div[@class='error-container -cx-PRIVATE-ErrorPage__errorContainer -cx-PRIVATE-ErrorPage__errorContainer__']")

                if errorContainer:
                    print(f"{to_unfollow} nicht mehr vorhanden!")
                    to_unfollow_db.unfollowed = "2099-09-09"
                    db.session.commit()
                    global nextsite
                    nextsite = 1

            except NoSuchElementException:
                nextsite = 0
                print("Seite aktiv")

            if nextsite == 0:

                print(f"Check 2: Check ob {to_unfollow} - Privat/Public?")
                logging.debug(f"Check 2: Check ob {to_unfollow} - Privat/Public?")

                try:
                    checkPublicAccount = driver.find_element_by_css_selector("h2.rkEop").text

                    #für private Accounts (=sie sind definitiv nicht mehr in Abonniertliste, nur für korrekte Abarbeitung)
                    if checkPublicAccount:
                        global public_account
                        public_account = 0
                        print(f"Check 2: privat")
                        logging.debug(f"Check 2: privat")

                        unfollowButton = driver.find_element_by_xpath("//button[@type='button']")
                        unfollowButtonText = driver.find_element_by_xpath("//button[@type='button']").text

                        if unfollowButtonText=="Anfrage gesendet":
                            print(unfollowButtonText)
                            print("Anfrage gesendet")

                            unfollowButton.click()

                            timer.scrollpause()

                            actions = ActionChains(driver)
                            actions.send_keys(Keys.TAB)
                            actions.send_keys(Keys.ENTER)
                            actions.perform()

                            to_unfollow_db.unfollowed = date
                            target_for_taskstatus.unfollowed = datetime.datetime.utcnow()

                            db.session.commit()

                            print(f"'Anfrage gesendet' zurückgenommen: {to_unfollow}")
                            logging.debug(f"'Anfrage gesendet': {to_unfollow}")
                        
                        elif unfollowButtonText=="Auch folgen":
                            print(unfollowButtonText)
                            print("'Auch folgen' => nichts machen!")

                            to_unfollow_db.unfollowed = date

                            db.session.commit()

                        elif unfollowButtonText=="Abonniert":
                            print(unfollowButtonText)
                            unfollowButton.click()

                            timer.powernap()

                            actions = ActionChains(driver)
                            actions.send_keys(Keys.TAB)
                            actions.send_keys(Keys.ENTER)
                            actions.perform()

                            timer.scrollpause()

                            to_unfollow_db.unfollowed = date
                            target_for_taskstatus.unfollowed = datetime.datetime.utcnow()

                            db.session.commit()

                            print(f"Enfolgt: {to_unfollow}")
                            logging.debug(f"Enfolgt: {to_unfollow}")

                        else:
                            print("Account ist privat, also nicht mehr in Abonniertliste!")
                            logging.debug("Account ist privat, also nicht mehr in Abonniertliste!")

                #für öffentliche Accounts (=sie sind definitiv noch in Abonniertliste)
                except NoSuchElementException:
                        public_account = 1
                        print(f"Check 2: öffentlich")
                        logging.debug(f"Check 2: öffentlich")

                        unfollowButton = driver.find_element_by_tag_name("button")
                        unfollowButtonText = driver.find_element_by_tag_name("button").text
                        print(f"Text Unfollow-Button: {unfollowButtonText}")

                        if unfollowButtonText=="Anfrage gesendet":
                            print(unfollowButtonText)
                            print("Anfrage gesendet")

                            unfollowButton.click()

                            timer.scrollpause()

                            actions = ActionChains(driver)
                            actions.send_keys(Keys.TAB)
                            actions.send_keys(Keys.ENTER)
                            actions.perform()

                            to_unfollow_db.unfollowed = date
                            target_for_taskstatus.unfollowed = datetime.datetime.utcnow()

                            db.session.commit()

                            print(f"'Anfrage gesendet' zurückgenommen: {to_unfollow}")
                            logging.debug(f"'Anfrage gesendet': {to_unfollow}")
                        
                        elif unfollowButtonText=="Auch folgen":
                            print(unfollowButtonText)
                            print("'Auch folgen' => nichts machen!")

                            to_unfollow_db.unfollowed = date
                            db.session.commit()

                        elif unfollowButtonText=="Abonniert":
                            print(unfollowButtonText)
                            unfollowButton.click()

                            timer.powernap()

                            actions = ActionChains(driver)
                            actions.send_keys(Keys.TAB)
                            actions.send_keys(Keys.ENTER)
                            actions.perform()

                            timer.scrollpause()

                            to_unfollow_db.unfollowed = date
                            target_for_taskstatus.unfollowed = datetime.datetime.utcnow()

                            db.session.commit()

                            print(f"Enfolgt: {to_unfollow}")
                            logging.debug(f"Enfolgt: {to_unfollow}")

                        else:
                            print("Account ist privat, also nicht mehr in Abonniertliste!")
                            logging.debug("Account ist privat, also nicht mehr in Abonniertliste!")

        timer.powernap()

        print(f"Checke Accounts mit t1-Timestamp")
        logging.debug(f"Checke Accounts mit t1-Timestamp")

        t1_unfollow_list = list()    #alle vergangenen t1, den targets muss entfolgt werden
        t1_like_list = list()        #alle t1 erst morgen, die targets müssen geliked werden

        t1_unfollow_db = Targets_done.query.filter(and_(Targets_done.t1_indicator=="yes", Targets_done.t1_timestamp<=date, Targets_done.unfollowed==None)).all()
        t1_like_db = Targets_done.query.filter(and_(Targets_done.t1_indicator=="yes", Targets_done.t1_timestamp>date, Targets_done.unfollowed==None, Targets_done.pics_liked==None)).all()

        for t1 in t1_unfollow_db:
            t1_unfollow_list.append(t1.target_url)
        print(f"Anzahl t1 Timestamp Accounts (unfollow): {len(t1_unfollow_list)}")
        logging.debug(f"Anzahl t1 Timestamp Accounts (unfollow): {len(t1_unfollow_list)}")

        for t1 in t1_like_db:
            t1_like_list.append(t1.target_url)
        print(f"Anzahl t1 Timestamp Accounts (liken): {len(t1_like_list)}")
        logging.debug(f"Anzahl t1 Timestamp Accounts (liken): {len(t1_like_list)}")

        print(f"Entfolge Accounts mit t1-Timestamp (t1-Timestamp <= {date})")
        logging.debug(f"Entfolge Accounts mit t1-Timestamp (t1-Timestamp <= {date})")

        for to_unfollow in t1_unfollow_list:

            target_for_taskstatus = Taskstatus(to_unfollow)
            db.session.add(target_for_taskstatus)
            db.session.commit()

            target_for_taskstatus = Taskstatus.query.filter_by(target_url=to_unfollow).first()

            to_unfollow_db = Targets_done.query.filter_by(target_url=to_unfollow).first()
            print(f"Entfolge: {to_unfollow_db.target_url} | t1-Timestamp: {to_unfollow_db.t1_timestamp}")
            logging.debug(f"Entfolge: {to_unfollow_db.target_url} | t1-Timestamp: {to_unfollow_db.t1_timestamp}")

            timer.powernap()

            driver.get(to_unfollow)

            timer.powernap()

            print(f"Check 1: Check ob {to_unfollow} noch existent?")
            logging.debug(f"Check 1: Check ob {to_unfollow} noch existent?")

            try:
                errorContainer = driver.find_element_by_xpath("//div[@class='error-container -cx-PRIVATE-ErrorPage__errorContainer -cx-PRIVATE-ErrorPage__errorContainer__']")

                if errorContainer:
                    print(f"{to_unfollow} nicht mehr vorhanden!")
                    to_unfollow_db.unfollowed = "2099-09-09"
                    db.session.commit()
                    nextsite = 1

            except NoSuchElementException:
                nextsite = 0
                print("Seite aktiv")

            if nextsite == 0:

                print(f"Check 2: Check ob {to_unfollow} - Privat/Public?")
                logging.debug(f"Check 2: Check ob {to_unfollow} - Privat/Public?")

                try:
                    checkPublicAccount = driver.find_element_by_css_selector("h2.rkEop").text

                    #für private Accounts
                    if checkPublicAccount:
                        public_account = 0
                        print(f"Check 2: privat")
                        logging.debug(f"Check 2: privat")

                        unfollowButton = driver.find_element_by_xpath("//button[@type='button']")
                        unfollowButtonText = driver.find_element_by_xpath("//button[@type='button']").text

                        if unfollowButtonText=="Anfrage gesendet":
                            print(unfollowButtonText)
                            print("Anfrage gesendet")

                            unfollowButton.click()

                            timer.scrollpause()

                            actions = ActionChains(driver)
                            actions.send_keys(Keys.TAB)
                            actions.send_keys(Keys.ENTER)
                            actions.perform()

                            to_unfollow_db.unfollowed = date

                            db.session.commit()

                            print(f"'Anfrage gesendet' zurückgenommen: {to_unfollow}")
                            logging.debug(f"'Anfrage gesendet': {to_unfollow}")
                        
                        elif unfollowButtonText=="Auch folgen":
                            print(unfollowButtonText)
                            print("'Auch folgen' => nichts machen!")

                            to_unfollow_db.unfollowed = "2099-09-09"
                            db.session.commit()

                        elif unfollowButtonText=="Abonniert":
                            print(unfollowButtonText)
                            unfollowButton.click()

                            timer.powernap()

                            actions = ActionChains(driver)
                            actions.send_keys(Keys.TAB)
                            actions.send_keys(Keys.ENTER)
                            actions.perform()

                            timer.scrollpause()

                            to_unfollow_db.unfollowed = date
                            target_for_taskstatus.unfollowed = datetime.datetime.utcnow()

                            db.session.commit()

                            print(f"Enfolgt: {to_unfollow}")
                            logging.debug(f"Enfolgt: {to_unfollow}")

                        else:
                            print("Account ist privat, also nicht mehr in Abonniertliste!")
                            logging.debug("Account ist privat, also nicht mehr in Abonniertliste!")

                            to_unfollow_db.unfollowed = "2099-09-09"
                            db.session.commit()

                #für öffentliche Accounts (=sie sind definitiv noch in Abonniertliste)
                except NoSuchElementException:
                        public_account = 1
                        print(f"Check 2: öffentlich")
                        logging.debug(f"Check 2: öffentlich")

                        unfollowButton = driver.find_element_by_tag_name("button")
                        unfollowButtonText = driver.find_element_by_tag_name("button").text
                        print(f"Text Unfollow-Button: {unfollowButtonText}")

                        if unfollowButtonText=="Anfrage gesendet":
                            print(unfollowButtonText)
                            print("Anfrage gesendet")

                            unfollowButton.click()

                            timer.scrollpause()

                            actions = ActionChains(driver)
                            actions.send_keys(Keys.TAB)
                            actions.send_keys(Keys.ENTER)
                            actions.perform()

                            to_unfollow_db.unfollowed = date
                            db.session.commit()

                            print(f"'Anfrage gesendet' zurückgenommen: {to_unfollow}")
                            logging.debug(f"'Anfrage gesendet': {to_unfollow}")
                        
                        elif unfollowButtonText=="Auch folgen":
                            print(unfollowButtonText)
                            print("'Auch folgen' => nichts machen!")

                            to_unfollow_db.unfollowed = "2099-09-09"

                            db.session.commit()

                        elif unfollowButtonText=="Abonniert":
                            print(unfollowButtonText)
                            unfollowButton.click()

                            timer.powernap()

                            actions = ActionChains(driver)
                            actions.send_keys(Keys.TAB)
                            actions.send_keys(Keys.ENTER)
                            actions.perform()

                            timer.scrollpause()

                            to_unfollow_db.unfollowed = date
                            target_for_taskstatus.unfollowed = datetime.datetime.utcnow()

                            db.session.commit()

                            print(f"Enfolgt: {to_unfollow}")
                            logging.debug(f"Enfolgt: {to_unfollow}")

                        else:
                            print("Account ist privat, also nicht mehr in Abonniertliste!")
                            logging.debug("Account ist privat, also nicht mehr in Abonniertliste!")

                            to_unfollow_db.unfollowed = "2099-09-09"
                            db.session.commit()

        print(f"Like Accounts mit t1-Timestamp (t1-Timestamp > {date})")
        logging.debug(f"Like Accounts mit t1-Timestamp (t1-Timestamp > {date})")

        for to_unfollow in t1_like_list:

            to_unfollow_db = Targets_done.query.filter_by(target_url=to_unfollow).first()

            print(f"{to_unfollow_db.target_url} | t1-Timestamp: {to_unfollow_db.t1_timestamp}")
            logging.debug(f"{to_unfollow_db.target_url} | t1-Timestamp: {to_unfollow_db.t1_timestamp}")
            driver.get(to_unfollow)
            timer.powernap()

            print(f"Check 1: Check ob {to_unfollow} noch existent?")
            logging.debug(f"Check 1: Check ob {to_unfollow} noch existent?")

            try:
                errorContainer = driver.find_element_by_xpath("//div[@class='error-container -cx-PRIVATE-ErrorPage__errorContainer -cx-PRIVATE-ErrorPage__errorContainer__']")

                if errorContainer:
                    print(f"{to_unfollow} nicht mehr vorhanden!")
                    to_unfollow_db.unfollowed = "2099-09-09"
                    db.session.commit()
                    nextsite = 1

            except NoSuchElementException:
                nextsite = 0
                print("Seite aktiv")

            if nextsite == 0:

                print(f"Check 2: Check ob {to_unfollow} - Privat/Public?")
                logging.debug(f"Check 2: Check ob {to_unfollow} - Privat/Public?")

                try:
                    checkPublicAccount = driver.find_element_by_css_selector("h2.rkEop").text

                    #für private Accounts (=sie sind definitiv nicht mehr in Abonniertliste, nur für korrekte Abarbeitung)
                    if checkPublicAccount:
                        public_account = 0
                        print(f"Check 2: privat")
                        logging.debug(f"Check 2: privat")

                #für öffentliche Accounts
                except NoSuchElementException:
                    public_account = 1

                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    timer.scrollpause()

                    hrefs = driver.find_elements_by_tag_name("a")

                    picHrefs = [elem.get_attribute("href") for elem in hrefs]
                    picHrefsFiltered = []

                    for url in picHrefs:
                        if "https://www.instagram.com/p/" in url:
                            picHrefsFiltered.append(url)

                    sliceZufall = random.randint(2, 5)

                    if len(picHrefsFiltered) > 0:#neu indention raus
                        #anzahl bilder entspricht anzahl zufallsauswahl"

                        target_for_taskstatus = Taskstatus(to_unfollow)
                        db.session.add(target_for_taskstatus)
                        db.session.commit()

                        target_for_taskstatus = Taskstatus.query.filter_by(target_url=to_unfollow).first()

                        print("###Liken von " + str(sliceZufall) + " Bildern")
                        picHrefsFilteredSliced = picHrefsFiltered[:sliceZufall]
                        pic_counter = 0

                        for pic in picHrefsFilteredSliced:
                            try:
                                driver.get(pic)
                                timer.powernap()
                                driver.find_element_by_xpath("//span[@class='fr66n']").click()
                                print(f"##Liked: {pic}")
                                logging.debug(f"##Liked: {pic}")
                                pic_counter = pic_counter + 1
                                timer.kurzschlafen()

                            except Exception:
                                timer.powernap()

                        target_for_taskstatus.pics_liked = pic_counter
                        db.session.commit()
                        to_unfollow_db.pics_liked = pic_counter
                        db.session.commit()

                        timer.langschlafen()
                        
        postprocessing_protocol = {'Status': 'postprocessing erledigt', 't5_accounts_unfollow': len(t5list), 't1_accounts_like': len(t1_like_list), 't1_accounts_unfollow': len(t1_unfollow_list)}

        return postprocessing_protocol
