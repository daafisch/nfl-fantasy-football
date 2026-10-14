import json
from yahoo_oauth import OAuth2

oauth = None

class Yahoo_Api():
    def __init__(self, consumer_key, consumer_secret,
                access_key):
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._access_key = access_key
        self._authorization = None
    def _login(self):
        global oauth
        oauth = OAuth2(None, None, from_file='./auth/oauth2yahoo.json')
        if not oauth.token_is_valid():
            oauth.refresh_access_token()

def load_yahoo_api(auth_path='./auth/oauth2yahoo.json'):
    with open(auth_path) as f:
        auths = json.load(f)
    return Yahoo_Api(auths['consumer_key'], auths['consumer_secret'], auths['access_token'])
