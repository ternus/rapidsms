#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


import urllib
import cgi

from threading import Thread
from SocketServer import ThreadingMixIn
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer


class Client(object):
    PROTOCOL_VERSION = "SPOMSKY/0.91"
    INCOMING_PORT = 8200
    
    
    class Server(ThreadingMixIn, HTTPServer):
        pass
    
    
    class RequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            
            # parse the form data (what
            # the hell *is* this junk?)
            form = cgi.FieldStorage(
                fp = self.rfile, 
                headers = self.headers,
                environ = {
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers["content-type"] })
            
            # if a callback has been registered (via
            # Client#subscribe), call it along with
            # the source (phone number), and contents
            if hasattr(self.server.spomsky_client, "callback"):
                self.server.spomsky_client.callback(
                    form["source"].value, form["body"].value)
            
            # always respond positively
            self.send_response(200)
            self.end_headers()
        
        # Does nothing except prevent HTTP
        # requests being echoed to the screen
        def log_request(*args):
            pass
    
    def __init__(self, server_host="localhost", server_port=8100):
        self.server_host = server_host
        self.server_port = server_port
        self.subscription_id = None
        self.server = None
    
    
    def __url(self, path):
        return "http://%s:%d/%s" % (self.server_host, self.server_port, path)
    
    
    def send(self, destination, body):
        
        # build the POST form
        data = urllib.urlencode({
            "version": self.PROTOCOL_VERSION,
            "destination": destination,
            "body": body
        })
        
        # attempt to POST to spomskyd
        f = urllib.urlopen(self.__url("send"), data)
        
        # read the response, even though we
        # don't care what it contains (for now)
        str = f.read()
        f.close()
        
        # return true if the message was successfully
        # sent, or false if (for whatever reason), it
        # was not. TODO: raise exception on failure?
        return (f.getcode() == 200)


    def subscribe(self, callback, my_host="localhost", my_port=INCOMING_PORT):
        
        # if we are already
        # subscribed, abort
        if self.server:
            return False
        
        # note down the callback, to be called
        # when a message arrives from the server
        self.callback = callback
        
        # create an HTTP server (to listen for callbacks from
        # the spomsky server, to notify us of incoming SMS)
        self.server = self.Server(("", my_port), self.RequestHandler)
        self.server.spomsky_client = self
        
        # start the server in a separate thread, and daemonize it
        # to prevent it from hanging once the main thread terminates
        self.thread = Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        # build the POST form
        data = urllib.urlencode({
            "version": self.PROTOCOL_VERSION,
            "host": my_host,
            "port": my_port,
            "path": "receiver"
        })
        
        # post the request to spomskyd, and fetch the response
        f = urllib.urlopen(self.__url("receive/subscribe"), data)
        str = f.read()
        f.close()
        
        # if the subscription was successful, store the uuid,
        # and return true to indicate that we're subscribed
        if (f.getcode() == 200):
            self.subscription_id = f.info()["x-subscription-uuid"]
            return True
        
        # something went wrong, so reset the subscription
        # id and return false. TODO: raise exception here?
        else:
            self.subscription_id = None
            return False
        
    
    def unsubscribe(self):
        
        # if we are subscribed, then send an HTTP
        # POST request to spomskyd to instruct it
        # to stop sending us messages
        if self.subscription_id:
            
            # build the POST form
            data = urllib.urlencode({
                "version": self.PROTOCOL_VERSION,
                "uuid": self.subscription_id
            })
            
            # post the request to spomskyd, and fetch the response
            f = urllib.urlopen(self.__url("receive/unsubscribe"), data)
            str = f.read()
            f.close()
        
        # unset instance vars
        self.callback = None
        self.server = None
        #self.thread.stop()
        self.thread = None
        
        # what could possibly
        # have gone wrong?
        return True

