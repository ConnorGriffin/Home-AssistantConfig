import appdaemon.plugins.hass.hassapi as hass

class BathroomVent(hass.Hass):

    def initialize(self):

        # Listen for the window to be open for <open_duration> seconds
        self.listen_state(
            callback = self.window_cb,
            entity = self.args['window'],
            old = 'off',
            new = 'on',
            duration = self.args['open_duration']
        )


    def window_cb(self, entity, attribute, old, new, kwargs):
        climate_control = self.get_state('binary_sensor.door_window_climate_control_active')
        if new == 'on' and climate_control != 'on':
            # Notify each person that's home if the window is left open, but not if other windows are open already
            self.log('Sending notification to shut bathroom window.')
            self.send_notification()


    def send_notification(self):
        for tracker in self.args['trackers']:
            if self.get_state(tracker['tracker']) == 'home':
                # Send a notification
                self.notify(
                    message = 'Bathroom done venting, please shut the window.',
                    name = 'html5',
                    target = tracker['notification_target'],
                    data = {
                        "tag": "bathroom-vent"
                    }
                )
