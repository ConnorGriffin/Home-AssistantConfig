import appdaemon.plugins.hass.hassapi as hass

class DoorWindow(hass.Hass):

    def initialize(self):
        self.data = {}
        for door in self.args.get("doors"):
            door_name = door.get('door')
            sensor = door.get('sensor')
            lock = door.get('lock')

            # Store some metadata here
            self.data[door_name] = {
                'waiting_unlocked': False,
                'waiting_closed': False
            }

            if sensor and lock:
                # Listen for each door to be closed and unlocked for a certain amount of time\
                self.listen_state(
                    cb = self.unlocked_cb,
                    entity = lock,
                    new = 'unlocked',
                    immediate = True,
                    duration = door.get('unlocked_seconds', self.args['door_unlocked_seconds']),
                    door = door_name,
                    lock = lock
                )
                self.listen_state(
                    cb = self.closed_cb,
                    entity = sensor,
                    new = 'Closed',
                    immediate = True,
                    duration = door.get('closed_seconds', self.args['door_closed_seconds']),
                    door = door_name,
                    lock = lock
                )


    def closed_cb(self, entity, attribute, old, new, kwargs):
        door = kwargs['door']
        lock = kwargs['lock']

        # If we were already waiting for the door to be closed, lock the door
        if self.data[door]['waiting_unlocked'] == True:
            self.log('{} closed, locking.'.format(door))
            self.call_service(
                service = 'lock/lock',
                entity_id = lock
            )
            self.data[door]['waiting_unlocked'] = False
        else:
            self.log('Waiting for {} to be unlocked.'.format(door))
            self.data[door]['waiting_closed'] = True


    def unlocked_cb(self, entity, attribute, old, new, kwargs):
        self.log('door unlocked')
        door = kwargs['door']
        lock = kwargs['lock']

        # If we were already waiting for the door to be closed, lock the door
        if self.data[door]['waiting_closed'] == True:
            self.log('{} unlocked, locking.'.format(door))
            self.call_service(
                service = 'lock/lock',
                entity_id = lock
            )
            self.data[door]['waiting_closed'] = False
        else:
            self.log('Waiting for {} to be closed.'.format(door))
            self.data[door]['waiting_unlocked'] = True