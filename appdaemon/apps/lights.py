import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime

class Lights(hass.Hass):

    def initialize(self):
        # Init an empty dict in the global_vars, used for storing data in various lights apps
        self.global_vars['lights'] = {}

        if "entities" in self.args:
            # Loop through the entities 
            for entity_id in self.args["entities"]:
                zwave_entity = 'zwave.{}'.format(entity_id)
                light_entity = 'light.{}'.format(entity_id)
                light_friendly = self.friendly_name(light_entity)

                self.global_vars['lights'][light_entity] = {
                    'override': None
                }


                # Listen for double taps
                self.log("Monitoring {} for double tap.".format(light_friendly), "INFO")
                self.listen_event(
                    self.double_tap_cb, 
                    "zwave.node_event", 
                    entity_id=zwave_entity, 
                    light_entity=light_entity
                )

                # Listen for light getting turned off
                self.log("Monitoring {} for turn off.".format(light_friendly), "INFO")
                self.listen_state(
                    self.turned_off_cb,
                    entity=light_entity,
                    new='off',
                    old='on'
                )

                # Listen for light getting turned on
                self.log("Monitoring {} for turn on.".format(light_friendly), "INFO")
                self.listen_state(
                    self.turned_on_cb,
                    entity=light_entity,
                    new='off',
                    old='on'
                )

                # Set auto-brightness every minute if light is on
                self.run_minutely(
                    self.auto_brightness_cb,
                    datetime.now().time(),
                    entity_id=light_entity
                )

    # Used by other functions to set overrides and store override data in the global_vars dictionary
    def set_override(self, entity_id, override, brightness_pct):
        setting = self.global_vars['lights'][entity_id]

        if setting['override'] == override:
            # Reset if the current action is called again (double tap once turns on, second time resets)
            setting['override'] = None
            self.auto_brightness_cb(dict(entity_id=entity_id))
        else:
            setting['override'] = override
            self.turn_on(entity_id, brightness_pct=brightness_pct)

    # Set max/min brightness on double tap up/down
    def double_tap_cb(self, event_name, data, kwargs):
        basic_level = data["basic_level"]
        zwave_entity = kwargs['entity_id']
        light_entity = kwargs['light_entity']
        light_friendly = self.friendly_name(light_entity)

        if basic_level == 255:
            direction = 'up'
            override = 'max_bright'
            brightness_pct = 100
        elif basic_level == 0:
            direction = 'down'
            override = 'min_bright'
            brightness_pct = 10
        else:
            return None

        self.log('{}: {}'.format(light_friendly, direction))
        self.set_override(light_entity, override, brightness_pct)

    # Nullify the override when a light is turned off
    def turned_off_cb(self, entity, attribute, old, new, kwargs):
        self.global_vars['lights'][entity]['override'] = None
    
    # Call auto_brightness_cb when a light is turned on 
    def turned_on_cb(self, entity, attribute, old, new, kwargs):
        self.log('{}: turned_on_cb'.format(entity))
        self.auto_brightness_cb(entity)
        
    # Set brightness automatically based on schedule
    def auto_brightness_cb(self, kwargs):
        entity_id = kwargs['entity_id']
        friendly_name = self.friendly_name(entity_id)
        state = self.get_state(entity_id)

        if state == 'on':
            setting = self.global_vars['lights'][entity_id]
            if not setting['override']:
                # Set auto-brightness if light is on and no override exists
                self.log("{}: Setting auto-brightness (placeholder)".format(friendly_name))
                # TODO: Determine brightness based on schedule
                #       Issue a turn-on command with the brightness percent