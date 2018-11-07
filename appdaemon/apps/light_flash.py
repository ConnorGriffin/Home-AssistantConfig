import appdaemon.plugins.hass.hassapi as hass
from time import sleep

class LightFlash(hass.Hass):

    def initialize(self):
        self.log('Loaded Light Flash')
        #self.flash_dumb_light('light.connors_office_light')


    def flash_cb(self, event_name, data, kwargs):
        none = None


    def set_brightness(self, kwargs):
        entity = kwargs.get('entity_id')
        brightness_pct = kwargs.get('brightness_pct')
        transition = kwargs.get('transition')
        self.turn_on(
            entity,
            brightness_pct = brightness_pct,
            transition = transition
        )


    def flash_dumb_light(self, entity_id, count=3, transition=0, flash_per_minute=60, **kwargs):
        brightness_pct = kwargs.get('brightness_pct', None)
        state = self.get_state(entity_id)
        if state == 'on':
            if not brightness_pct:
                brightness_pct = self.get_state(entity_id, attribute='brightness') / 2.55

            first_brightness = 1
            second_brightness = brightness_pct
        else:
            if not brightness_pct:
                brightness_pct = 100
            first_brightness = brightness_pct
            second_brightness = 1

        base_delay = 60 / flash_per_minute
        current_delay = 0
        for i in range(count):
            add_delay = base_delay + transition
            first_delay = current_delay + add_delay
            second_delay = first_delay + add_delay
            current_delay = second_delay

            self.run_in(
                callback = self.set_brightness,
                seconds = first_delay,
                entity_id = entity_id,
                brightness_pct = first_brightness,
                transition = transition
            )
            self.run_in(
                callback = self.set_brightness,
                seconds = second_delay,
                entity_id = entity_id,
                brightness_pct = second_brightness,
                transition = transition
            )