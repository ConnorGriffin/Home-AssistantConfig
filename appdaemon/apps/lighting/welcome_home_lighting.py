# Welcome Home automation - Turns on lights when someone returns home between certain hours.
# Uses Schlage connect to detect if lights should be turned on/off, since normal presence detection isn't fast enough

import appdaemon.plugins.hass.hassapi as hass

class WelcomeHomeLighting(hass.Hass):

    def initialize(self):

        # Listen for lock to change to unlocked at the keypad (avoid keyturn triggering)
        self.listen_state(
            cb = self.returned_home_cb,
            entity = 'sensor.front_door_lock_alarm_type',
            new = '19',
            type = 'lock'
        )

        # Listen for return_home events
        for entity in self.args.get('presence_sensors', []):
            self.listen_state(
                cb = self.returned_home_cb,
                entity = entity,
                old = 'off',
                new = 'on',
                type = 'presence'
            )

    def returned_home_cb(self, entity, attribute, old, new, kwargs):
        # Turn on lights if sun is down and someone unlocks the front door
        if self.sun_down():
            lights = self.args['lights']
            if kwargs['type'] == 'lock':
                self.log('Lock unlocked, turning on lights.')
            elif kwargs['type'] == 'presence':
                self.log('{} returned home, turning on lights.'.format(self.friendly_name(entity)))

            # Turn on each light if it isn't already on
            for light in lights:
                current_state = self.get_state(light)
                if current_state == 'off':
                    self.turn_on_and_refresh(
                        kwargs = {'entity_id': light}
                    )

                    # Turn off the lights after a set time if auto_off is specified
                    auto_off = self.args.get('auto_off', None)
                    if auto_off:
                        self.run_in(
                            self.turn_off_and_refresh,
                            seconds = auto_off,
                            entity_id = light
                        )


    def refresh_zwave_entity(self, kwargs):
        entity_id = kwargs.get('entity_id')
        self.call_service(
            service = 'zwave/refresh_entity',
            entity_id = entity_id
        )


    def turn_off_and_refresh(self, kwargs):
        entity_id = kwargs.get('entity_id')
        # Turn off, then refresh the light entity to get accurate data
        self.turn_off(entity_id)
        self.run_in(
            self.refresh_zwave_entity,
            seconds = 1,
            entity_id = entity_id
        )


    def turn_on_and_refresh(self, kwargs):
        entity_id = kwargs.get('entity_id')
        # Override automatic brightness if brightness_pct is specified:
        brightness_pct = self.args.get('brightness_pct', None)
        if brightness_pct:
            # Set the light mode to Manual before turning on (override auto-brightness)
            mode_entity = 'input_select.{}_mode'.format(entity_id.split('.')[1])
            self.call_service(
                service = 'input_select/select_option',
                entity_id = mode_entity,
                option = 'Manual'
            )
            self.turn_on(entity_id, brightness_pct=self.args['brightness_pct'])

        # Turn on, then refresh the light entity to get accurate data
        self.turn_on(entity_id)
        self.run_in(
            self.refresh_zwave_entity,
            seconds = 1,
            entity_id = entity_id
        )
