import appdaemon.plugins.hass.hassapi as hass

class LowBattery(hass.Hass):

    def initialize(self):
        # Init an empty dict in the global_vars, used for storing data
        self.global_vars['battery'] = {}

        # Iterate over the entity list, setting listeners, etc.
        for entity in self.args.get('entities',[]):
            # Set the alerting state, used to only fire one notification
            self.global_vars['battery'][entity] = {
                'alerting': False,
            }

            # Configure listeners
            self.listen_state(
                cb = self.low_battery_cb,
                entity = entity,
                attribute = 'battery_level',
                immediate = True
            )


    def low_battery_cb(self, entity, attribute, old, new, kwargs):
        level = self.args.get('level', 10)
        alerting = self.global_vars['battery'][entity].get('alerting', False)

        if new <= level and not alerting:
            # Set the alerting status and send an alert notification
            self.global_vars['battery'][entity]['alerting'] = True
            self.notify(
                title = 'ALERT: Low Battery: {} '.format(self.friendly_name(entity)),
                message = '{} reported a battery level of {}%, which is below the notification threshold of {}%'.format(entity, new, level),
                name = 'email'
            )
            self.log('Sent low battery email for {}'.format(entity))
        elif new > level and alerting:
            # Reset the alerting status and send a reset notification
            self.global_vars['battery'][entity]['alerting'] = False
            self.notify(
                title = 'RESET: Low Battery: {} '.format(self.friendly_name(entity)),
                message = 'Low battery level alert has been reset for entity {}. Battery is at {}%.'.format(entity, new),
                name = 'email'
            )
            self.log('Sent alert reset email for {}'.format(entity))