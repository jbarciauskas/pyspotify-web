import web
import logging
import logging.config
import threading
import json
import datetime
import thread

from web import form
from jukebox import Jukebox
from threading import Condition
from spotify import Link

logging.config.fileConfig("logging.conf")
web.jukebox = None
jukeboxCondition = Condition()

render = web.template.render('templates/', base='wrapper')
urls = (
        '/', 'index',
        '/login', 'login',
        '/playlists', 'playlists',
        '/listtracks/(.*)', 'listtracks',
        '/play/(.*)/(.*)', 'play',
        '/search', 'search',
        '/logout', 'logout',
        )
app = web.application(urls, globals())

def redirectWhenNotLoggedIn():
    if not web.jukebox and not web.ctx.path == '/login' and not web.ctx.path == 'favicon.ico':
        print "Redirecting back to login"
        raise web.seeother('/login')

app.add_processor(web.loadhook(redirectWhenNotLoggedIn))

LoginForm = form.Form(
        form.Textbox("username", form.notnull),
        form.Password('password', form.notnull),
        form.Button('Login'))

class login:
    def GET(self):
        loginForm = LoginForm()
        return render.loginTemplate(loginForm)

    def POST(self):
        loginForm = LoginForm()
        if not loginForm.validates():
            return self.onBadLogin(loginForm)
        else:
            try:
                web.jukebox = Jukebox(jukeboxCondition, loginForm.d.username, loginForm.d.password, True)
                thread.start_new_thread(web.jukebox.connect, ())
                jukeboxCondition.acquire()
                jukeboxCondition.wait()
                jukeboxCondition.release()
                raise web.seeother('/')
            except Exception as e:
                logging.error(e)
                raise e

    def onBadLogin(self, loginForm):
        return render.loginTemplate(loginForm);

class index:
    def GET(self):
        raise web.seeother('/playlists')

class status:
    def GET(self):
        web.header('Content-Type', 'application/json')
        return json.dumps(GlobalsManager.getPlayer().getCurrentSongAsDict())

class playlists:
    def GET(self):
        for playlist in web.jukebox.ctr:
            while(not playlist.is_loaded()):
                pass
        return render.playlists(web.jukebox.ctr)

class listtracks:
    def GET(self, playlistId):
        return render.listtracks(playlistId, web.jukebox.ctr[int(playlistId)])

class play:
    def GET(self, playlistId, trackId):
        web.jukebox.load(int(playlistId), int(trackId))
        web.jukebox.play()
        return render.nowPlaying(web.jukebox.ctr[int(playlistId)][int(trackId)])

class search:
    def POST(self):
        self.results = None
        def search_finished(results, userdata):
            resultsRendered = []
            for a in results.tracks():
                resultsRendered.append(dict(link=Link.from_track(a, 0), name=a.name()))
            self.results = resultsRendered
            jukeboxCondition.acquire()
            jukeboxCondition.notify()
            jukeboxCondition.release()
        input = web.webapi.input('searchString')
        searchString = input['searchString']
        web.jukebox.search(searchString, search_finished)
        jukeboxCondition.acquire()
        jukeboxCondition.wait()
        jukeboxCondition.release()
        return render.searchResults(self.results)

class logout:
    def GET(self):
        web.jukebox.disconnect()
        web.jukebox = None
        raise web.seeother('/login')

if __name__=="__main__":
    web.internalerror = web.debugerror
    app.run()
