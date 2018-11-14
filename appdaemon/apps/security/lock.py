import appdaemon.plugins.hass.hassapi as hass

class Lock(hass.Hass):

    # TODO: Don't unlock if the door has been unlocked/locked in the last few minutes
    # TODO: Integrate with new presence sensors, stop listening for events directly

    def initialize(self):
        self.trackers = {}

        for tracker in self.args['trackers']:
            tracker_name = tracker['tracker_name']

            # Store some metadata here, needed since there's no listen_event oneshots and passing handles is weird
            self.trackers[tracker_name] = {
                'listening': False,
                'handle':    None
            }

            # Wait for the person to not be home for the specified duration
            self.listen_state(
                cb = self.not_home_cb,
                entity = tracker['tracker'],
                new = 'not_home',
                duration = self.args['not_home_duration'],
                immediate = True,
                notification_target = tracker.get('notification_target', None),
                tracker_name = tracker_name
            )


    def not_home_cb(self, entity, attribute, old, new, kwargs):
        tracker_name = kwargs['tracker_name']
        self.log('Arming, waiting for {} to return home.'.format(tracker_name))

        # Listen for the person to return home
        handle = self.listen_event(
            cb = self.returned_home_cb,
            event = 'returned_home',
            name = tracker_name,
            notification_target = kwargs.get('notification_target', None)
        )

        # Store the listen_event data so we can cancel it later
        self.trackers[tracker_name]['listening'] = True
        self.trackers[tracker_name]['handle'] = handle


    def returned_home_cb(self, event_name, data, kwargs):
        lock_friendly = self.friendly_name(self.args['lock_entity'])
        name = data['name']
        notification_target = kwargs.get('notification_target', None)
        settings = self.trackers[name]


        # Cancel listening and reset settings (like a oneshot for listen_event)
        self.cancel_listen_event(settings['handle'])
        settings['listening'] = False
        settings['handle'] = None

        # Fire an event back to HomeAssistant, other apps can subscribe to this
        self.fire_event(
            "returned_home",
            source = 'AppDaemon',
            name = name
        )

        # Unlock the door
        self.log('{} has returned, unlocking {}.'.format(name, lock_friendly))
        self.call_service(
            service = 'lock/unlock',
            entity_id = self.args['lock_entity']
        )

        # Send a notification if a notification_target is provided, will probably turn this off after testing
        if notification_target:
            self.notify(
                message = '{} unlocked.'.format(lock_friendly),
                name = 'gcm_html5',
                target = notification_target
            )
