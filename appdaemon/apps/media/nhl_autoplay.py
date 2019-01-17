import appdaemon.plugins.hass.hassapi as hass
import requests
from datetime import timezone, time, timedelta, datetime

class NHLAutoplay(hass.Hass):

    def initialize(self):
        self.debug = True

        self.run_daily(
            callback = self.get_schedule,
            start = time(9, 0, 0)
        )
        self.run_once(
            callback = self.get_schedule,
            start = self.time()
        )


    def get_schedule(self, kwargs):
        # Get the Bruins schedule for today, include the broadcast data
        schedule = requests.get('https://statsapi.web.nhl.com/api/v1/schedule?teamId=6&expand=schedule.broadcasts').json()

        # Setup a listener if there is a game today
        if schedule['dates']:
            game = schedule['dates'][0]['games'][0]
            game_date = self.utc_to_local(self.convert_utc(game['gameDate']))
            now = self.datetime().replace(tzinfo=timezone.utc).astimezone(tz=None)

            if now <= game_date or self.debug:
                # Order the broadcasts the way they'd appear in the Roku app so we can navigate to them properly
                available = []
                for broadcast_type in ['home', 'away', 'national']:
                    for broadcast in game['broadcasts']:
                        if broadcast['type'] == broadcast_type:
                            available.append(broadcast_type)

                # Determine which broadcast to use (prefer local over national)
                if game['teams']['home']['team']['id'] == 6:
                    location = 'home'
                else:
                    location = 'away'

                # Store the index of the broadcast, this is how many times to move right to select the broadcast in the Roku app
                if location in available:
                    chosen_broadcast = available.index(location)
                else:
                    chosen_broadcast = available.index('national')

                ## At game_start plus 7 minutes (typical start delay for a game), start listening for me to come home if I'm not already home
                self.run_at(
                    callback = self.game_start,
                    start = # game start + 7 minutes,
                    chosen_broadcast = chosen_broadcast
                    #etc.
                )


    def utc_to_local(self, utc_dt):
        return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)


"""


# Setup a notification listener
self.listen_event(
    self.start_watching_cb,
    #etc.
)

def game_start(self, kwargs):
    # Check if I'm home, if not, start a oneshot listener for me to return home


def return_home(self, kwargs):
    # Check if the projector is already on.
    # If so, do nothing
    # If not, send a notification asking if you want to start watching the game


def start_watching(self, kwargs):
    # If I say 'yes' to the notification, do the following:
    # - Turn on the projector
    # - Set the roku to the NHL app

    # Look into whether or not we can issue roku remote control commands.
    # If yes, press down, choose the appropriate broadcast, and press 'Start from beginning', then fast forward 6 minutes.


def roku_remote(self, kwargs):

"""
