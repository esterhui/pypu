#!/usr/bin/python2

# This code logs us into facebook once, obtained from:
# http://blog.carduner.net/2010/05/

import os.path
import json
import urllib2
import urllib
import urlparse
import BaseHTTPServer
import webbrowser
 
APP_ID = '401958849934497'
APP_SECRET = '7b84ba01b576c1ff128c130d11b658d2'
ENDPOINT = 'graph.facebook.com'
REDIRECT_URI = 'http://localhost:8080/'
ACCESS_TOKEN = None
TOKEN_FILE = os.path.join(os.environ['HOME'],'.fb_access_token')

STATUS_TEMPLATE = u"{name}\033[0m: {message}"
 
def get_url(path, args=None):
    args = args or {}
    if ACCESS_TOKEN:
        args['access_token'] = ACCESS_TOKEN
    if 'access_token' in args or 'client_secret' in args:
        endpoint = "https://"+ENDPOINT
    else:
        endpoint = "http://"+ENDPOINT
    return endpoint+path+'?'+urllib.urlencode(args)
 
def get(path, args=None):
    return urllib2.urlopen(get_url(path, args=args)).read()
 
class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
 
    def do_GET(self):
        global ACCESS_TOKEN
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
 
        code = urlparse.parse_qs(urlparse.urlparse(self.path).query).get('code')
        code = code[0] if code else None
        if code is None:
            self.wfile.write("Sorry, authentication failed.")
            sys.exit(1)
        response = get('/oauth/access_token', {'client_id':APP_ID,
                                               'redirect_uri':REDIRECT_URI,
                                               'client_secret':APP_SECRET,
                                               'code':code})
        ACCESS_TOKEN = urlparse.parse_qs(response)['access_token'][0]
        open(TOKEN_FILE,'w').write(ACCESS_TOKEN)
        self.wfile.write("You have successfully logged in to facebook. "
                         "You can close this window now.")
 
def get_fb_token():
    """Returns access token, optionally launches browser session 
    to get the token via a facebook login.
    esterhui: got this code from the interweb, but can't find the reference now.
    """
    global ACCESS_TOKEN
    if not os.path.exists(TOKEN_FILE):
        print "Logging you in to facebook..."
        webbrowser.open(get_url('/oauth/authorize',
                                {'client_id':APP_ID,
                                 'redirect_uri':REDIRECT_URI,
                                 'scope':'manage_pages,publish_stream,photo_upload,user_photos,video_upload'}))
 
        httpd = BaseHTTPServer.HTTPServer(('127.0.0.1', 8080), RequestHandler)
        while ACCESS_TOKEN is None:
            httpd.handle_request()
    else:
        ACCESS_TOKEN = open(TOKEN_FILE).read()

    return ACCESS_TOKEN
