import os
from dotenv import load_dotenv

load_dotenv()

class Settings(object):
	port = int(os.environ.get("MY_APP_PORT"))
	cookie_user = os.environ.get("MY_COOKIE_USER")
	cookie_user_token = cookie_user + "-token"
	cookie_secret = os.environ.get("MY_COOKIE_SECRET")

	aud = os.environ.get("MY_INSTANT_CONNECT_AUD")
	org_ids = os.environ.get("MY_ORG_IDS").split(",")
	users = os.environ.get("MY_USERS", [])
	if users != []:
		users = users.split(',')

	fedramp_client_id = os.environ.get("MY_FEDRAMP_CLIENT_ID")
	fedramp_client_secret = os.environ.get("MY_FEDRAMP_SECRET")
	
	webex_client_id = os.environ.get("MY_WEBEX_CLIENT_ID")
	webex_client_secret = os.environ.get("MY_WEBEX_SECRET")
	webex_base_uri = os.environ.get("MY_WEBEX_BASE_URI")
	webex_redirect_uri = webex_base_uri + "/webex-oauth"
	webex_scopes = os.environ.get("MY_WEBEX_SCOPES")

	aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
	aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
