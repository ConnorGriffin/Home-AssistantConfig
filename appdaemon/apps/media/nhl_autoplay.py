import appdaemon.plugins.hass.hassapi as hass
import requests
from datetime import timezone, time, timedelta, datetime

class NHLAutoplay(hass.Hass):

    def initialize(self):
        self.return_home_handle = None
        self.debug = False

        # Check the schedule every day at 9 AM
        self.run_daily(
            callback = self.get_schedule,
            start = time(10, 0, 0)
        )

        self.run_once(
            callback = self.get_schedule,
            start = self.time()
        )

        # Listen for the notification to be clicked
        self.listen_event(
            cb = self.notification_clicked,
            event = 'html5_notification.clicked',
            tag = 'nhl-autoplay'
        )



    def get_schedule(self, kwargs):
        self.log('Getting NHL schedule.')
        # Cancel any existing return_home listeners
        if self.return_home_handle:
            self.cancel_listen_state(self.return_home_handle)

        # Get the Bruins schedule for today, include the broadcast data
        schedule = requests.get('https://statsapi.web.nhl.com/api/v1/schedule?teamId=6&expand=schedule.broadcasts').json()

        # Setup a listener if there is a game today
        if schedule['dates']:
            game = schedule['dates'][0]['games'][0]
            game_date = self.utc_to_local(self.convert_utc(game['gameDate']))
            now = datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(tz=None)

            if now <= game_date or self.debug:
                self.log('Game today at {}.'.format(game_date.strftime('%-I:%M %p')))
                # Order the broadcasts the way they'd appear in the Roku app so we can navigate to them properly
                available = []
                for broadcast_type in ['home', 'away', 'national']:
                    for broadcast in game['broadcasts']:
                        if broadcast['type'] == broadcast_type:
                            available.append(broadcast_type)

                # Determine which broadcast to use (prefer local over national)
                if game['teams']['home']['team']['id'] == 6:
                    proponent_location = 'home'
                    opponent_location = 'away'
                else:
                    proponent_location = 'away'
                    opponent_location = 'home'

                # Store the index of the broadcast, this is how many times to move right to select the broadcast in the Roku app
                if proponent_location in available:
                    chosen_broadcast = available.index(proponent_location)
                else:
                    chosen_broadcast = available.index('national')

                # Get other game details to pass to the notification sender
                opponent_id = game['teams'][opponent_location]['team']['id']
                proponent_id = game['teams'][proponent_location]['team']['id']
                opponent = requests.get('https://statsapi.web.nhl.com/api/v1/teams/{}'.format(opponent_id)).json()
                proponent = requests.get('https://statsapi.web.nhl.com/api/v1/teams/{}'.format(proponent_id)).json()
                opponent_name = opponent['teams'][0]['locationName']
                proponent_name = proponent['teams'][0]['locationName']

                # At game_start, start listening for me to come home if I'm not already home
                self.log('At {} a listener will arm for Connor to return home.'.format(game_date.strftime('%-I:%M %p')))
                self.run_at(
                    callback = self.game_start,
                    start = game_date.replace(tzinfo=None),
                    chosen_broadcast = chosen_broadcast,
                    proponent_location = proponent_location,
                    opponent_name = opponent_name,
                    proponent_name = proponent_name,
                    scheduled_start = game_date,
                    content_url = 'https://statsapi.web.nhl.com{}'.format(game['content']['link'])
                )
        else:
            self.log('No games today.')


    def game_start(self, kwargs):
        # Check if I'm home, if not, start a oneshot listener for me to return home
        presence = self.get_state(self.args['presence'])
        if presence != 'on':
            self.log('Waiting for Connor to return home.')
            self.return_home_handle = self.listen_state(
                cb = self.returned_home,
                entity = self.args['presence'],
                new = 'on',
                old = 'off',
                chosen_broadcast = kwargs['chosen_broadcast'],
                proponent_location = kwargs['proponent_location'],
                opponent_name = kwargs['opponent_name'],
                proponent_name = kwargs['proponent_name'],
                scheduled_start = kwargs['scheduled_start'],
                content_url = kwargs['content_url']
            )


    def returned_home(self, entity, attribute, old, new, kwargs):
        # Cancel listening (doing this because oneshots don't work)
        self.cancel_listen_state(kwargs['handle'])
        self.return_home_handle = None

        self.log('Connor returned home, sending game start notification.')

        # Format the notification message
        if kwargs['proponent_location'] == 'away':
            separator = '@'
        else:
            separator = 'vs'
        team_details = '{} {} {} - {}'.format(kwargs['proponent_name'], separator, kwargs['opponent_name'], kwargs['scheduled_start'].strftime('%-I:%M %p'))

        # Send a notification asking if I want to watch the game
        self.notify(
            title = 'NHL Autoplay',
            message = 'Do you want to watch the game?\n{}'.format(team_details),
            name = 'gcm_html5',
            target = self.args['notification_targets'],
            data = {
                'tag': 'nhl-autoplay',
                'icon': '/local/icons/nhl.png',
                'actions': [{
                    'action': 'yes',
                    'title': 'Yes'
                }, {
                    'action': 'no',
                    'title': 'No'
                }],
                'chosen_broadcast': kwargs['chosen_broadcast'],
                'content_url': kwargs['content_url']
            }
        )


    # Take action based on notification actions
    def notification_clicked(self, event_name, data, kwargs):
        game_over = False
        # If the notification action is yes, turn on the roku and start the game
        if data['action'] == 'yes':
            # Determine if the game is over or not, figure out how many "clicks" to the right to select the proper broadcast
            chosen_broadcast = data['data']['chosen_broadcast']
            game_content = requests.get(data['data']['content_url']).json()
            for stream in game_content['media']['epg']:
                # Recap and Extended Highlights show up before the NHL.tv broadcasts, so if they're in the list we need to move the
                # cursor to the right to select the full game feeds
                if stream['title'] in ['Recap', 'Extended Highlights']:
                    if stream['items']:
                        game_over = True
                        chosen_broadcast += 1

            if game_over:
                down_count = 1
            else:
                down_count = 2

            # Open the NHL app on the Roku
            self.call_service(
                service = 'media_player/select_source',
                entity_id = self.args['roku_entity'],
                source = 'NHL'
            )

            # Select the game on the home screen (defaults to favorite team's latest game)
            self.run_in(
                self.roku_remote,
                seconds = 20,
                action = 'Select'
            )

            # Wait for game details to load, then find the broadcast
            self.run_in(
                self.roku_remote,
                seconds = 30,
                action = 'Down'
            )
            for i in range(chosen_broadcast):
                self.run_in(
                    self.roku_remote,
                    seconds = 32+i,
                    action = 'Right'
                )
            for i in range(down_count):
                self.run_in(
                    self.roku_remote,
                    seconds = 35+i,
                    action = 'Down'
                )
            self.run_in(
                self.roku_remote,
                seconds = 37,
                action = 'Select'
            )

            # Fast Forward to about 7 minutes in. Don't use 32x, not enough precision here
            for i in range(3):
                self.run_in(
                    self.roku_remote,
                    seconds = 53+i,
                    action = 'Fwd'
                )
            self.run_in(
                self.roku_remote,
                seconds = 67,
                action = 'Play'
            )


    def roku_remote(self, kwargs):
        requests.post('http://{}:8060/keypress/{}'.format(self.args['roku_ip'], kwargs['action']))


    def utc_to_local(self, utc_dt):
        return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)
