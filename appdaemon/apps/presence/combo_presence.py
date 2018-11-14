# Combo Presence - Combines device tracker and Tasker for quicker presence detection
# Uses device tracker for general home/away. Tasker can fire an event to instantly change to Home.
# Allows for faster 'home' detection than nmap/router for time sensitive automations (ex: door unlock when home)

import appdaemon.plugins.hass.hassapi as hass

class ComboPresence(hass.Hass):

    def initialize(self):
        self.trackers = {}

        for tracker in self.args['trackers']:
            device_tracker = tracker['device_tracker']
            tracker_name = tracker['name']
            presence_sensor = tracker['presence_sensor']

            # Store some metadata here, needed since there's no listen_event oneshots and passing handles is weird
            self.trackers[tracker_name] = {
                'handle': None
            }

            # Get the device tracker state and convert to bool
            device_tracker_state = self.get_state(device_tracker)
            if device_tracker_state == 'home':
                new_state = 'on'
            elif device_tracker_state == 'not_home':
                new_state = 'off'

            # Create the sensor
            self.set_state(
                entity_id = presence_sensor,
                state = new_state,
                attributes = {
                    'friendly_name': tracker_name,
                    'device_class': 'presence'
                }
            )

            # Listen for their device to report as not_home
            self.listen_state(
                cb = self.device_tracker_cb,
                entity = device_tracker,
                tracker_name = tracker_name,
                presence_sensor = presence_sensor
            )


    def device_tracker_cb(self, entity, attribute, old, new, kwargs):
        tracker_name = kwargs['tracker_name']
        presence_sensor = kwargs['presence_sensor']

        if new == 'not_home':
            # Set state to off
            new_state = 'off'

            # If the new state is 'not_home', listen for a tasker event to set state to home
            handle = self.listen_event(
                cb = self.returned_home_cb,
                event = 'returned_home',
                name = tracker_name,
                presence_sensor = presence_sensor
            )

            # Store the listen_event data so we can cancel it later
            self.trackers[tracker_name]['handle'] = handle
        elif new == 'home':
            # Set state to on
            new_state = 'on'

            # If the new state is 'home', cancel any pending event listeners if there are any
            handle = self.trackers[tracker_name]['handle']
            if handle:
                self.cancel_listen_event(handle)
                self.trackers[tracker_name]['handle'] = False

        # Update the sensor with the device tracker state info
        self.set_state(presence_sensor, state=new_state)


    def returned_home_cb(self, event_name, data, kwargs):
        name = data['name']
        settings = self.trackers[name]

        # Cancel the handle and reset settings (like a oneshot for listen_event)
        self.cancel_listen_event(settings['handle'])
        settings['handle'] = None

        # Update the sensor status
        self.set_state(kwargs['presence_sensor'], state='on')
