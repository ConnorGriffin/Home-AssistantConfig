import appdaemon.plugins.hass.hassapi as hass

class Lock(hass.Hass):

    # TODO: Don't unlock if the door has been unlocked/locked in the last few minutes
    # TODO: Add an automation switch

    def initialize(self):
        # Wait for the person to not be home for the specified duration
        self.listen_state(
            cb = self.not_home_cb,
            entity = self.args['connor_tracker'],
            new = 'not_home',
            duration = self.args['not_home_duration'],
            immediate = True
        )


    def not_home_cb(self, entity, attribute, old, new, kwargs):
        self.log('Arming, waiting for {} to return home.'.format(self.friendly_name(entity)))
        # Listen for the person to return home
        self.listen_state(
            cb = self.home_cb,
            entity = entity,
            new = 'home',
            oneshot = True
        )
        self.notify(
            message = '{} will unlock when you return home.'.format(self.friendly_name(self.args['lock_entity'])),
            name = 'simplepush_connor'
        )


    def home_cb(self, entity, attribute, old, new, kwargs):
        lock_friendly = self.friendly_name(self.args['lock_entity'])
        person_friendly = self.friendly_name(entity)

        # Unlock the door if Diana is not home (during testing)
        if self.get_state(self.args['diana_tracker']) == 'not_home':
            self.log('{} has returned, unlocking {}.'.format(person_friendly, lock_friendly))
            self.call_service(
                service = 'lock/unlock',
                entity_id = self.args['lock_entity']
            )
            self.notify(
                message = '{} unlocked.'.format(lock_friendly),
                name = 'simplepush_connor'
            )
        else:
            self.log('{} has returned but Diana is home, not unlocking {}.'.format(person_friendly, lock_friendly))
            self.notify(
                message = '{} not unlocked because Diana is home.'.format(lock_friendly),
                name = 'simplepush_connor'
            )
