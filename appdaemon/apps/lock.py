import appdaemon.plugins.hass.hassapi as hass

class Lock(hass.Hass):

    # TODO: Don't unlock if the door has been unlocked/locked in the last few minutes

    def initialize(self):
        for tracker in self.args['trackers']:
            # Wait for the person to not be home for the specified duration
            self.listen_state(
                cb = self.not_home_cb,
                entity = tracker['tracker'],
                new = 'not_home',
                duration = self.args['not_home_duration'],
                immediate = True,
                notify_name = tracker.get('notify_name', None)
            )


    def not_home_cb(self, entity, attribute, old, new, kwargs):
        self.log('Arming, waiting for {} to return home.'.format(self.friendly_name(entity)))
        # Listen for the person to return home
        self.listen_state(
            cb = self.home_cb,
            entity = entity,
            new = 'home',
            notify_name = kwargs.get('notify_name', None)
        )


    def home_cb(self, entity, attribute, old, new, kwargs):
        # Cancel listening (doing this because oneshots don't work)
        self.cancel_listen_state(kwargs['handle'])

        lock_friendly = self.friendly_name(self.args['lock_entity'])
        person_friendly = self.friendly_name(entity)
        notify_name = kwargs.get('notify_name', None)

        # Unlock the door if Diana is not home (during testing)
        self.log('{} has returned, unlocking {}.'.format(person_friendly, lock_friendly))
        self.call_service(
            service = 'lock/unlock',
            entity_id = self.args['lock_entity']
        )
        if notify_name:
            self.notify(
                message = '{} unlocked.'.format(lock_friendly),
                name = notify_name
            )
