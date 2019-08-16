import appdaemon.plugins.hass.hassapi as hass

class DoorAutoUnlock(hass.Hass):

    # TODO: Don't unlock if the door has been unlocked/locked in the last few minutes
    # TODO: Integrate with new presence sensors, stop listening for events directly

    def initialize(self):
        for tracker in self.args['trackers']:
            tracker_name = tracker['tracker_name']

            # Wait for the person to not be home for the specified duration
            self.listen_state(
                cb = self.presence_cb,
                entity = tracker['tracker'],
                new = 'not_home',
                duration = self.args['not_home_duration'],
                immediate = True,
                notification_target = tracker.get('notification_target'),
                tracker_name = tracker_name
            )


    def presence_cb(self, entity, attribute, old, new, kwargs):
        notification_target = kwargs.get('notification_target')
        tracker_name = kwargs['tracker_name']

        # Setup listeners if the new state is off (away)
        if new == 'not_home':
            self.log('Waiting for {} to return home.'.format(tracker_name))

            # Listen for the person to return home
            self.listen_state(
                cb = self.presence_cb,
                entity = entity,
                new = 'home',
                notification_target = notification_target,
                tracker_name = tracker_name
            )
        elif new == 'home':
            # Unlock the door if the new state is on (home)
            lock = self.args['lock_entity']
            lock_friendly = self.friendly_name(lock)

            # Cancel listening and reset settings (like a oneshot for listen_event)
            self.cancel_listen_state(kwargs.get('handle'))

            # Unlock the door
            self.log('{} has returned, unlocking {}.'.format(tracker_name, lock_friendly))
            self.call_service(
                service = 'lock/unlock',
                entity_id = lock
            )

            # Send a notification if a notification_target is provided, will probably turn this off after testing
            if notification_target:
                self.notify(
                    message = '{} unlocked.'.format(lock_friendly),
                    name = 'html5',
                    target = notification_target
                )
