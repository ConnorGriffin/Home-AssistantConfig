# Welcome Home automation - Turns on lights when someone returns home between certain hours.
# Uses Schlage connect to detect if lights should be turned on/off, since normal presence detection isn't fast enough

import appdaemon.plugins.hass.hassapi as hass

class WelcomeHomeLighting(hass.Hass):

    def initialize(self):
        # Store future scheduler call details here so we can cancel/extend them as needed
        self.handles = []
        self.lights = []

        # Set the automation state
        self.set_automation_state({'state': 'off'})

        # Listen for lock to change to unlocked at the keypad (avoid keyturn triggering)
        self.listen_state(
            cb = self.returned_home_cb,
            entity = 'sensor.front_door_lock_alarm_type',
            new = '19',
            type = 'lock'
        )

        # Wait for each person to be not_home for a set duration, which will trigger another listen_state waiting for them to return
        for entity in self.args.get('presence_sensors', []):
            self.listen_state(
                cb = self.not_home_cb,
                entity = entity,
                new = 'not_home',
                duration = self.args['not_home_duration'],
                immediate = True,
                type = 'presence'
            )


    def not_home_cb(self, entity, attribute, old, new, kwargs):
        # Setup a oneshot listen_state that will fire when the person returns
        self.log('Waiting for {} to return home.'.format(self.friendly_name(entity)))
        self.listen_state(
            cb = self.returned_home_cb,
            entity = entity,
            old = 'not_home',
            new = 'home',
            type = 'presence'
        )


    def returned_home_cb(self, entity, attribute, old, new, kwargs):
        trigger_type = kwargs['type']

        if trigger_type == 'presence':
            # Cancel listening (doing this because oneshots don't work)
            self.cancel_listen_state(kwargs['handle'])

        # Turn on lights if sun is down and someone unlocks the front door
        if self.sun_down():
            if trigger_type == 'lock':
                self.log('Lock unlocked, turning on lights.')
            elif trigger_type == 'presence':
                self.log('{} returned home, turning on lights.'.format(self.friendly_name(entity)))

            auto_off = self.args.get('auto_off', 300)

            # If automation is already triggered, just extend the existing timers
            automation_state = self.get_state(self.args['state_sensor'])
            if automation_state == 'on':
                # Cancel any existing timers
                for handle in self.handles:
                    self.cancel_timer(handle)
                self.handles = []

                # Set lights equal to the previously activated lights instead of all lights
                lights = self.lights
                self.lights = []
            else:
                lights = self.args['lights']

            # Set the automation state
            self.set_automation_state({'state': 'on'})
            handle = self.run_in(
                self.set_automation_state,
                seconds = auto_off,
                state = 'off'
            )
            self.handles.append(handle)

            # Turn on each light if it isn't already on
            for light in lights:
                current_state = self.get_state(light)
                if current_state == 'off' or automation_state == 'on':
                    # Turn on the light and refresh the zwave details
                    self.turn_on_and_refresh(
                        kwargs = {'entity_id': light}
                    )

                    # Add to the light array so we know which lights we've turned on (for extending times on multiple welcome homes)
                    if light not in self.lights:
                        self.lights.append(light)

                    # Turn off the lights after a set time
                    handle = self.run_in(
                        self.turn_off_and_refresh,
                        seconds = auto_off,
                        entity_id = light
                    )
                    self.handles.append(handle)


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

        if entity_id in self.lights:
            self.lights.remove(entity_id)


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


    def set_automation_state(self, kwargs):
        state = kwargs['state']
        # Set the automation status sensor state
        self.set_state(
            entity_id = self.args['state_sensor'],
            state = state,
            attributes = {
                'friendly_name': 'Welcome Home Lighting',
                'icon': 'mdi:lightbulb-on'
            }
        )

        # Cleare the handles list if automation is changing to off
        if state == 'off':
            self.handles = []