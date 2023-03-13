import json
import traceback
import urllib.parse

import tornado.gen
import tornado.web

#from base64 import b64encode
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from handlers.base import BaseHandler

from spark import Spark
from settings import Settings

class WebexOAuthHandler(BaseHandler):

    def build_access_token_payload(self, code, client_id, client_secret, redirect_uri):
        payload = "client_id={0}&".format(client_id)
        payload += "client_secret={0}&".format(client_secret)
        payload += "grant_type=authorization_code&"
        payload += "code={0}&".format(code)
        payload += "redirect_uri={0}".format(redirect_uri)
        return payload

    @tornado.gen.coroutine
    def get_tokens(self, code, environment):
        print('generating token for environment:{0}'.format(environment))
        if environment == "fedramp":
            url = "https://api-usgov.webex.com/v1/access_token"
            api_url = 'https://api-usgov.webex.com/v1'
            payload = self.build_access_token_payload(code, Settings.fedramp_client_id, Settings.fedramp_client_secret, Settings.webex_redirect_uri)
        else:
            environment = ""
            url = "https://webexapis.com/v1/access_token"
            api_url = 'https://webexapis.com/v1'
            payload = self.build_access_token_payload(code, Settings.webex_client_id, Settings.webex_client_secret, Settings.webex_redirect_uri)
        headers = {
            'cache-control': "no-cache",
            'content-type': "application/x-www-form-urlencoded"
            }
        success = False
        try:
            request = HTTPRequest(url, method="POST", headers=headers, body=payload)
            http_client = AsyncHTTPClient()
            response = yield http_client.fetch(request)
            resp = json.loads(response.body.decode("utf-8"))
            print("WebexOAuthHandler.get_tokens /access_token Response: {0}".format(resp))
            person = yield Spark(resp['access_token']).get_with_retries_v2('{0}/people/me'.format(api_url))
            print("person.body:{0}".format(person.body))
            if not self.is_allowed(person.body):
                self.redirect('/authentication-failed')
            else:
                self.save_current_user(person, resp['access_token'], environment)
                success = True
        except Exception as e:
            print("WebexOAuthHandler.get_tokens Exception:{0}".format(e))
            traceback.print_exc()
        raise tornado.gen.Return(success)

    def handle_redirect(self, environment, complex_redirect):
        if(len(complex_redirect) <= 1):
            self.redirect("/"+environment)
        else:
            #TODO - test this (unauthenticated workflow for both meeting starting now and not yet.)
            complex_path = urllib.parse.unquote_plus(complex_redirect[1])
            print('redirect to complex path:{0}'.format(complex_path))
            self.redirect(complex_path)
            

    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        response = "Error"
        try:
            print('Webex OAuth: {0}'.format(self.request.full_url()))
            state = self.get_argument("state","")
            print('Webex OAuth state:{0}'.format(state))
            complex_redirect = state.split('-',1)
            environment = complex_redirect[0]
            if environment == "fedramp":
                person = self.get_current_user("fedramp")
            else:
                person = self.get_current_user()
            if not person:
                if self.get_argument("code", None):
                    code = self.get_argument("code")
                    success = yield self.get_tokens(code, environment)
                    if success:
                        self.handle_redirect(environment, complex_redirect)
                    return
                else:
                    authorize_url = '{0}?client_id={1}&response_type=code&redirect_uri={2}&scope={3}&state={4}'
                    if environment == "fedramp":
                        use_url = "https://api-usgov.webex.com/v1/authorize"
                        authorize_url = authorize_url.format(use_url, Settings.fedramp_client_id, urllib.parse.quote_plus(Settings.webex_redirect_uri), Settings.webex_scopes, urllib.parse.quote_plus(state))
                    else:
                        use_url = 'https://webexapis.com/v1/authorize'
                        authorize_url = authorize_url.format(use_url, Settings.webex_client_id, urllib.parse.quote_plus(Settings.webex_redirect_uri), Settings.webex_scopes, urllib.parse.quote_plus(state))
                    print("WebexOAuthHandler.get authorize_url:{0}".format(authorize_url))
                    self.redirect(authorize_url)
                    return
            else:
                print("Already authenticated.")
                self.handle_redirect(environment, complex_redirect)
                return
        except Exception as e:
            response = "{0}".format(e)
            print("WebexOAuthHandler.get Exception:{0}".format(e))
            traceback.print_exc()
        self.write(response)
