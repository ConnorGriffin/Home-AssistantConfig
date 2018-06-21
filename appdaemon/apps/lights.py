import appdaemon.plugins.hass.hassapi as hass

class Lights(hass.Hass):

    def initialize(self):
        # Init an empty dict in the global_vars, used for storing data in various lights apps
        self.global_vars['lights'] = {}

        if "entities" in self.args:
            # Loop through the entities 
            for entity_id in self.args["entities"]:
                zwave_entity = 'zwave.{}'.format(entity_id)
                light_entity = 'light.{}'.format(entity_id)

                self.global_vars['lights'][light_entity] = {
                    'override': None
                }


                self.log("Monitoring {} for double tap.".format(
                    self.friendly_name(light_entity)), "INFO")

                # Listen for double taps
                self.listen_event(
                    self.double_tap_cb, 
                    "zwave.node_event", 
                    entity_id=zwave_entity, 
                    light_entity=light_entity
                )

    # Used by other functions to set overrides and store override data in the global_vars dictionary
    def set_override(self, entity_id, override, brightness_pct):
        setting = self.global_vars['lights'][entity_id]

        if setting['override'] == override:
            # Reset if the current action is called again (double tap once turns on, second time resets)
            setting['override'] = None
            # callback the scheduling code here
        else:
            setting['override'] = override
            self.turn_on(entity_id, brightness_pct=brightness_pct)

    def double_tap_cb(self, event_name, data, kwargs):
        basic_level = data["basic_level"]
        zwave_entity = kwargs['entity_id']
        light_entity = kwargs['light_entity']

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

        self.log('{}: {}'.format(self.friendly_name(light_entity), direction))
        self.set_override(light_entity, override, brightness_pct)
    