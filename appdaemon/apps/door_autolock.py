import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime

class DoorAutolock(hass.Hass):

    def initialize(self):
        for door in self.args.get("doors"):
            door_name = door.get('door')
            sensor = door.get('sensor')
            lock = door.get('lock')

            if sensor and lock:
                unlocked_seconds = door.get('unlocked_seconds', self.args['unlocked_seconds'])
                closed_seconds = door.get('closed_seconds', self.args['closed_seconds'])

                # Listen for each door to be closed and unlocked for a certain amount of time
                self.listen_state(
                    cb = self.unlocked_cb,
                    entity = lock,
                    new = 'unlocked',
                    immediate = True,
                    duration = unlocked_seconds,
                    door_name = door_name,
                    door_sensor = sensor,
                    lock = lock,
                    closed_seconds = closed_seconds
                )
                self.listen_state(
                    cb = self.closed_cb,
                    entity = sensor,
                    new = 'off',
                    immediate = True,
                    duration = closed_seconds,
                    door_name = door_name,
                    lock = lock,
                    unlocked_seconds = unlocked_seconds
                )


    def closed_cb(self, entity, attribute, old, new, kwargs):
        door_name = kwargs['door_name']
        lock = kwargs['lock']
        unlocked_seconds = kwargs['unlocked_seconds']

        # Figure out how long it's been since the door lock status changed
        lock_state = self.get_state(lock, attribute='all')
        now = datetime.utcnow()
        lock_state_time = self.convert_utc(lock_state['last_changed']).replace(tzinfo=None)
        since_changed_seconds = (now - lock_state_time).total_seconds()

        # If the lock has been unlocked for the required time, lock it
        if lock_state['state'] == 'unlocked' and since_changed_seconds >= unlocked_seconds:
            self.log('{} closed and unlocked, locking.'.format(door_name))
            self.call_service(
                service = 'lock/lock',
                entity_id = lock
            )


    def unlocked_cb(self, entity, attribute, old, new, kwargs):
        door_name = kwargs['door_name']
        door_sensor = kwargs['door_sensor']
        lock = kwargs['lock']
        closed_seconds = kwargs['closed_seconds']

        # Figure out how long it's been since the door open/closed status changed
        door_state = self.get_state(door_sensor, attribute='all')
        now = datetime.utcnow()
        door_state_time = self.convert_utc(door_state['last_changed']).replace(tzinfo=None)
        since_changed_seconds = (now - door_state_time).total_seconds()

        # If the door has been closed for the required time, lock it
        if door_state['state'] == 'off' and since_changed_seconds >= closed_seconds:
            self.log('{} closed and unlocked, locking.'.format(door_name))
            self.call_service(
                service = 'lock/lock',
                entity_id = lock
            )
