import json
import traceback
import tornado.gen
import tornado.web
import urllib.parse
from settings import Settings
from spark import Spark

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self, environment=""):
        person = self.get_secure_cookie(Settings.cookie_user+environment, max_age_days=1, min_version=2)
        token = self.get_secure_cookie(Settings.cookie_user_token+environment, max_age_days=1, min_version=2)
        if type(token) == bytes:
            token = token.decode('utf-8')
        if person:
            person = json.loads(person)
            person.update({"token":token})
        return person

    def save_current_user(self, person, token, environment=""):
        self.set_secure_cookie(Settings.cookie_user+environment, json.dumps(person.body), expires_days=1, version=2)
        self.set_secure_cookie(Settings.cookie_user_token+environment, token, expires_days=1, version=2)
    
    def delete_current_user(self, environment=""):
        self.clear_cookie(Settings.cookie_user+environment)
        self.clear_cookie(Settings.cookie_user_token+environment)
    
    def unencoded_scopes(self):
        return Settings.webex_scopes.replace("%20", " ").replace("%3A", ":")

    def load_main_page(self, person):
        #print(person)
        print('loading main page')
        #tokens = {"token":self.application.settings['db'].is_user(person['id'])}
        self.render("index.html", person=person)

    def load_page(self, environment=""):
        try:
            print('load_page environment:{0}'.format(environment))
            person = self.get_current_user(environment)
            print('load_page person:{0}'.format(person))
            if not person:
                args = ""
                if environment != "":
                    args = '?state={0}'.format(environment)
                self.redirect('/webex-oauth{0}'.format(args))
            else:
                self.load_main_page(person)
        except Exception as e:
            traceback.print_exc()
    
    def is_allowed(self, person):
        is_org_user = person["orgId"] in Settings.org_ids
        is_allowed_user = person.get("emails", [None])[0] in Settings.users
        return is_org_user or is_allowed_user

    def redirect_page(self, redirect_path):
        for arg in self.request.arguments:
            if arg not in ["returnTo", "token"]:
                arg_val = self.request.arguments[arg][0].decode('utf-8')
                if arg_val != "":
                    redirect_path += '{0}={1}&'.format(arg, arg_val)
        self.redirect(redirect_path)

    @tornado.gen.coroutine
    def get_handler(self, environment=""):
        try:
            print("get_handler:")
            token = self.get_argument('token', None)
            return_to = self.get_argument('returnTo', "")
            print(self.request.arguments)
            print('token:{0}'.format(token))
            if token:
                if environment == "fedramp":
                    person = yield Spark(token).get_with_retries_v2('https://api-usgov.webex.com/v1/people/me')
                else:
                    person = yield Spark(token).get_with_retries_v2('https://webexapis.com/v1/people/me')
                print("person.body:{0}".format(person.body))
                if not self.is_allowed(person.body):
                    redirect_path = '/authentication-failed?'
                    if return_to != "":
                        redirect_path += 'returnTo={0}&'.format(return_to)
                    self.redirect_page(redirect_path)
                else:
                    self.save_current_user(person, token, environment)
                    self.redirect_page("/{0}?".format(return_to))
            else:
                self.load_page(environment)
        except Exception as e:
            traceback.print_exc()
