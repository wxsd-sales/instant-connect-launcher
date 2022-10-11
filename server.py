#!/usr/bin/env python
import base64
import boto3
import os
import json
import pytz
import re
import requests
import traceback
import urllib.parse

#from apscheduler.schedulers.tornado import TornadoScheduler
from aws_requests_auth.aws_auth import AWSRequestsAuth
from datetime import datetime, timedelta
from icalendar import Calendar, Event, vCalAddress, vText
#from io import BytesIO
from pathlib import Path
from threading import Thread
#from requests_toolbelt import MultipartEncoder
from uuid import uuid4


import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web

from settings import Settings
from spark import Spark
from handlers.base import BaseHandler
from handlers.qr import QRHandler
from handlers.oauth import WebexOAuthHandler

from tornado import queues
from tornado.options import define, options, parse_command_line
from tornado.httpclient import HTTPError#, AsyncHTTPClient, HTTPRequest

define("debug", default=False, help="run in debug mode")

class LogoutHandler(BaseHandler):
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        try:
            print("LogoutHandler GET")
            print(self.request.full_url())
            return_to = self.get_argument('returnTo', "")
            print('return_to:{0}'.format(return_to))
            if return_to == "fedramp":
                fedramp_person = self.get_current_user('fedramp')
                if fedramp_person:
                    print('deleting fedramp person')
                    self.delete_current_user('fedramp')
                    #print(fedramp_person.get('emails')[0])
                    redirect_to = "https://idbroker-f.webex.com/idb/saml2/jsp/doSSO.jsp?type=logout"#&email={0}".format(fedramp_person.get('emails')[0])
                    self.redirect(redirect_to)
                else:
                    self.redirect_page('/{0}?'.format(return_to))
            else:
                person = self.get_current_user()
                if person:
                    print('deleting commercial person')
                    self.delete_current_user()
                self.redirect_page('/{0}?'.format(return_to))
            
        except Exception as e:
            traceback.print_exc()

class AuthFailedHandler(BaseHandler):
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        try:
            print("AuthFailedHandler GET")
            self.render("authentication-failed.html")
        except Exception as e:
            traceback.print_exc()

class InvalidMeetingHandler(BaseHandler):
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        try:
            print("InvalidMeetingHandler GET")
            self.render("invalid.html")
        except Exception as e:
            traceback.print_exc()


class FedrampHandler(BaseHandler):
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        yield self.get_handler("fedramp")

class MainHandler(BaseHandler):
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        yield self.get_handler()


class CommandHandler(BaseHandler):

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        #requests to /meet come here
        environment = self.get_argument('environment')
        host_data = self.get_argument('data')
        print('command handler GET environment:{0}'.format(environment))
        person = self.get_current_user(environment)
        print('command handler GET person:{0}'.format(person))
        if not person:
            state = urllib.parse.quote_plus(self.request.uri)
            print("command handler GET state:{0}".format(state))
            args = '?state={0}'.format(environment + "-" + state)
            self.redirect('/webex-oauth{0}'.format(args))
        else:
            conversation_id = yield self.start_instant_connect(environment, host_data, Spark(person["token"]))
            if(conversation_id):
                base_url = 'https://instant.webex.com'
                if environment == "fedramp":
                    base_url = 'https://instant-usgov.webex.com'
                redirect_url = '{0}/hc/v1/login?int=jose&v=1&data={1}'.format(base_url, host_data)
                print(redirect_url)
                self.redirect(redirect_url)
            else:
                self.redirect('/invalid')

    @tornado.gen.coroutine
    def post(self):
        print("CommandHandler request.body:{0}".format(self.request.body))
        jbody = json.loads(self.request.body)
        command = jbody.get('command',"")
        environment = jbody.get('environment',"")
        person = self.get_current_user(environment)
        print("CommandHandler, person: {0}".format(person))
        result_object = {"reason":None, "code":200, "data":None}
        if not person:
            result_object['reason'] = 'Not Authenticated with Webex.'
            result_object['code'] = 401
        else:
            #user = self.application.settings['db'].get_user(person['id'])
            if not self.is_allowed(person): #and user == None:
                result_object['reason'] = 'Not Authenticated.'
                result_object['code'] = 403
            elif command not in ['start_meeting', 'email']:
                result_object['reason'] = "{0} command not recognized.".format(command)
                result_object['code'] = 400
            else:
                result = None
                try:
                    start_time = jbody.get('start_time')
                    duration = jbody.get('duration')
                    timezone = jbody.get('timezone')
                    start_date, end_date = self.get_dates(start_time, duration, timezone)
                    if command == 'start_meeting':
                        success, data = yield self.start_meeting(person, environment, start_date, end_date)
                        if not success:
                            result_object.update(data)
                        else:
                            result = data
                    elif command == 'email':
                        url = jbody.get('url')
                        email = jbody.get('email')
                        if url:
                            if email:
                                addresses = []
                                error = False
                                recompiler = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$") 
                                for address in email.split(","):
                                    address = address.strip()
                                    match = recompiler.search(address)
                                    if address != "" and match != None:
                                        addresses.append(address)
                                    else:
                                        error = True
                                        result_object['reason'] = "'{0}' is not recognized as a valid email address.".format(address)
                                        result_object['code'] = 400
                                if not error:
                                    if len(addresses) > 0:
                                        yield self.email_guests(addresses, person, url, start_date, end_date)
                                        result = True
                                        print('done with queue')
                                    else:
                                        result_object['reason'] = "Please enter one or more valid email addresses, separated by commas.".format(address)
                                        result_object['code'] = 400
                            else:
                                result_object['reason'] = "missing required json parameter 'email' for email command."
                                result_object['code'] = 400
                        else:
                            result_object['reason'] = "missing required json parameter 'url' for email command."
                            result_object['code'] = 400
                except HTTPError as he:
                    traceback.print_exc()
                    result_object['reason'] = he.response.reason
                    result_object['code'] = he.code
                if result != None:
                    result_object["data"] = result
        res_val = json.dumps(result_object)
        print(res_val)
        self.write(res_val)

    def get_mtg_urls(self, environment):
        talk_url = "https://instant.webex.com/hc/v1/talk?"
        mtg_broker_url = "https://mtg-broker-a.wbx2.com/api/v1"
        if environment == "fedramp":
            talk_url = "https://instant-usgov.webex.com/hc/v1/talk?"
            mtg_broker_url = "https://mtg-broker.gov.ciscospark.com/api/v1"
        print('mtg_broker_url:{0}'.format(mtg_broker_url))
        print('talk_url:{0}'.format(talk_url))
        return mtg_broker_url, talk_url


    def get_start_date(self, start_time, timezone):
        start_date = datetime.strptime(start_time, '%m/%d/%Y %H:%M')
        print(start_date.timestamp())
        pytimezone = pytz.timezone(timezone)
        start_date = pytimezone.localize(start_date).astimezone(pytz.timezone('UTC'))
        print('start_date:{0}'.format(start_date))
        return start_date

    def get_end_date(self, start_date, duration):
        end_date = start_date + timedelta(minutes=duration)
        print('end_date:{0}'.format(end_date))
        return end_date

    def get_dates(self, start_time, duration, timezone):
        start_date = self.get_start_date(start_time, timezone)
        end_date = self.get_end_date(start_date, duration)
        return start_date, end_date

    @tornado.gen.coroutine
    def start_instant_connect(self, environment, host_data, userSpark):
        conversation_id = None
        mtg_broker_url, talk_url = self.get_mtg_urls(environment)
        mtg_url = '{0}/space/?int=jose&data='.format(mtg_broker_url)
        mtg_url += host_data
        try:
            mtg_resp = yield userSpark.post_with_retries(mtg_url, allow_nonstandard_methods=True)
            print("start_meeting - mtg_resp:{0}".format(mtg_resp.body))
            space_id = mtg_resp.body.get("spaceId")
            if(environment == "fedramp"):
                space_id += '=='
            conversation_id = base64.b64decode(space_id).decode('utf-8')
            conversation_id = conversation_id.split('/ROOM/')[1].strip()
        except Exception as e:
            traceback.print_exc()
        raise tornado.gen.Return(conversation_id)

    def create_ics(self, start_date, end_date, subject, url, body, person):
        cal = Calendar()
        event = Event()
        event.add('summary', subject)
        event.add('dtstart', start_date)
        event.add('dtend', end_date)
        event.add('dtstamp', datetime.now(pytz.UTC))

        organizer = vCalAddress('MAILTO:{0}'.format(person["emails"][0]))
        organizer.params['cn'] = vText(person["displayName"])
        event['organizer'] = organizer
        event['location'] = vText(url)
        event['description'] = body
        # Adding events to calendar
        cal.add_component(event)
        
        filedata = cal.to_ical()
        print(filedata)
        #print(BytesIO(filedata))
        #print(open('sample.ics', 'rb'))
        return filedata

    @tornado.gen.coroutine
    def start_meeting(self, person, environment, start_date, end_date):
        mtg_broker_url, talk_url = self.get_mtg_urls(environment)
        success = False
        result = {'reason':"Unable to Encrypt Data", 'code':400}
        userSpark = Spark(person["token"])
        jose_url = '{0}/joseencrypt'.format(mtg_broker_url)
        jwt_dict = {"sub": uuid4().hex, 'nbf':int(start_date.timestamp()), 'exp':int(end_date.timestamp())}
        print('jwt_dict:{0}'.format(jwt_dict))
        payload = { "aud": Settings.aud, "jwt": jwt_dict}
        jose_resp = yield userSpark.post_with_retries(jose_url, payload)
        print("start_meeting - jose_resp:{0}".format(jose_resp.body))
        host_data = jose_resp.body.get("host", [None])[0]
        guest_data = jose_resp.body.get("guest", [None])[0]
        if host_data != None:
            conversation_id = None
            delay = False
            now = datetime.now(pytz.UTC)
            print('now:{0}'.format(now))
            seconds_until_start = (start_date - now).total_seconds()
            print('difference:{0}'.format(seconds_until_start))
            if seconds_until_start < 300:
                conversation_id = yield self.start_instant_connect(environment, host_data, userSpark)
            else:
                delay = True
                subject = "Your Scheduled Instant Connect Meeting"
                url = Settings.webex_base_uri + "/meet?environment={0}&data={1}".format(environment, host_data)
                body = "When it's time to begin your meeting, "
                body += '<a href="{0}">Click Here</a>.'.format(url)
                filedata = self.create_ics(start_date, end_date, subject, url, body, person)
                yield self.email_threads(subject, body, [person["emails"][0]], filedata)
            talk_url = '{0}int=jose&v=1&data='.format(talk_url)
            host_url = talk_url.replace('talk', 'login') + host_data
            guest_url = talk_url + guest_data
            result = {"host_url" :host_url, "guest_url": guest_url, "conversationId": conversation_id, "delay":delay}
            success = True
        raise tornado.gen.Return((success, result))


    def get_headers_auth(self, credentials, hostname):
        headers = {
                    'Content-Type': 'application/json',
                    'host': hostname
                }
        #print(credentials.access_key)
        #print(credentials.secret_key)
        auth = AWSRequestsAuth(aws_access_key=credentials.access_key,
                            aws_secret_access_key=credentials.secret_key,
                            aws_token=credentials.token,
                            aws_host=hostname,
                            aws_region='us-east-1',
                            aws_service='execute-api')
        return headers, auth

    @tornado.gen.coroutine
    def email_guests(self, addresses, person, url, start_date, end_date):
        seconds_until_start = (start_date - datetime.now(pytz.UTC)).total_seconds()
        print('email_guests difference:{0}'.format(seconds_until_start))
        if seconds_until_start < 300:
            starting_now = " that is <b>starting now!</b>"
            subject_now = " Starts Now"
            body_now = "To"
        else:
            starting_now = "."
            subject_now = ""
            body_now = "When it is time to"
        body = "{0} ({1}) is inviting you to join an Instant Connect meeting{2}<br><br>".format(person["displayName"], person["emails"][0], starting_now)
        body += "{0} join this meeting, ".format(body_now)
        body += '<a href="{0}">Click Here</a>'.format(url)
        subject = "Instant Connect Meeting{0}".format(subject_now)
        filedata = self.create_ics(start_date, end_date, subject, url, body, person)
        yield self.email_threads(subject, body, addresses, filedata)

    def send_email(self, subject, body, email, filedata, q):
        #print(url)
        #print(email)
        #print(q)
        #url = url.replace('/login?', '/talk?')
        session = boto3.Session(aws_access_key_id=Settings.aws_access_key_id, aws_secret_access_key=Settings.aws_secret_access_key)
        credentials = session.get_credentials()
        filename = "sample.ics"
        hostname = 'o66zb2gfej.execute-api.us-east-1.amazonaws.com'
        headers, auth = self.get_headers_auth(credentials, hostname)

        body = {
            "alertType":"wxpdemoEmail",
            "alertDestinations": [ email ],
            "alertBody": {
                "Html": {
                    "Data": body
               }
            },
            "alertMeta": "metadata",
            "alertParams": {
                "subject":subject,
                "parameterValue":"value",
                "attachment": "https://wxsdattachments.s3.us-west-1.amazonaws.com/" + filename,
                "attachmentType": "text",
                "attachmentSubtype": "calendar"
            }
        }

        print('Email File Step 1')
        put_val = None
        try:
            url = "https://{0}/default/wxsdAttachmentUpload".format(hostname)
            response = requests.post(url, json={"key":filename} , headers=headers, auth=auth)
            print(response)
            print("response.content:{0}".format(response.content))
            try:
                content = json.loads(response.content.decode('utf-8'))
                print(content)
                print('Email File Step 2')
                files = { 'file': filedata }
                r = requests.post(content['url'], data=content['fields'], files=files) 
                print(r)
                print("r.content:{0}".format(r.content))
                print('Email File Step 3')
                headers, auth = self.get_headers_auth(credentials, 'alerts.wbx.ninja')
                response = requests.post('https://alerts.wbx.ninja/alerts', json=body, headers=headers, auth=auth)
                print(response)
                print("response.content:{0}".format(response.content))
                put_val = response.content
            except Exception as e:
                traceback.print_exc()
        except HTTPError as he:
            traceback.print_exc()
            print(he)
        q.put(put_val)
        return True
    
    @tornado.gen.coroutine
    def email_threads(self, subject, body, addresses, filedata=None):
        q = queues.Queue(maxsize=len(addresses))
        threads = []
        for address in addresses:
            t = Thread(target=self.send_email, args=[subject, body, address, filedata, q], daemon=True)
            t.start()
            threads.append(t)
        for address in addresses:
            print('waiting for queue...')
            yield q.get()
        for t in threads:
            t.join()


@tornado.gen.coroutine
def main():
    try:
        parse_command_line()
        app = tornado.web.Application([
                (r"/", MainHandler),
                (r"/fedramp", FedrampHandler),
                (r"/meet", CommandHandler),
                (r"/command", CommandHandler),
                (r"/webex-oauth", WebexOAuthHandler),
                (r"/authentication-failed", AuthFailedHandler),
                (r"/invalid", InvalidMeetingHandler),
                (r"/qr", QRHandler),
                (r"/logout", LogoutHandler)
              ],
            template_path=os.path.join(os.path.dirname(__file__), "html_templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            cookie_secret=Settings.cookie_secret,
            xsrf_cookies=False,
            debug=options.debug,
            )
        server = tornado.httpserver.HTTPServer(app)
        server.bind(Settings.port)
        print("main - Serving... on port {0}".format(Settings.port))
        server.start()
        tornado.ioloop.IOLoop.instance().start()
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    main()
