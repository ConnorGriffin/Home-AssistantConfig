import appdaemon.plugins.hass.hassapi as hass

#
#
# SETUP
# https://community.home-assistant.io/t/ge-14294-and-jasco-equivilant-zwave-dimmer-double-tap-event-on-associaton-group-3-need-config-help/29469/17
#
# Forward double-tap events to your controller. In the Z-Wave configuration panel of HA:
# Select the node for the light switch you want to enable double-tap on.
# Under Node group associations select Group 3
# Under Node to control select your Z-Wave USB stick (or whatever Z-Wave controller you use).
# Hit Add to Group
#
#
# Args:
# entities:
#   - entity: Zwave entity to monitor for double tap.
#     events:
#       - tap_up: List of actions to fire on double tap up.
#           - action_entity: Entity to perform action on. Ex: light.living_room_light
#             action: Action to perform. 'on' or 'off'
#       - tap_down: List of actions to fire on double tap down.
#           - action_entity: Entity to perform action on. Ex: light.living_room_light
#             action: Action to perform. 'on' or 'off'
#
# NOTE: the triggering entity does not turn on by default and will need to be added as an action_entity if you would like it to.
#
#
# FULL EXAMPLE
#
# Double Tap Switch:
#   class: zwave_double_tap
#   module: zwave_double_tap
#   entities:
#     - entity: zwave.island_lights
#       events:
#         - tap_up:
#             - action_entity: light.living_room_light_level
#               action: 'on'
#             - action_entity: light.living_room_lamp_level
#               action: 'on'
#         - tap_down:
#             - action_entity: light.living_room_light_level
#               action: 'off'
#
#
# Version 1.0:
#   Initial Version


class zwave_double_tap(hass.Hass):

    def initialize(self):
        if "entities" in self.args:
            # Loop through the entities 
            for entity_id in self.args["entities"]:
                # Init an empty dict in the data dict, used for storing data on the entity
                self.app_config['Double Tap Switch']['data'][entity_id] = {}

                self.log("Monitoring {} for double tap.".format(
                    self.friendly_name(entity_id)), "INFO")

                self.listen_event(
                    self.zwave_event, "zwave.node_event", entity_id=entity_id)

    def zwave_event(self, event_name, data, kwargs):
        # Can't calculate time deltas with self.datetime() for some reason, need to use datetime
        from datetime import datetime

        basic_level = data["basic_level"]
        entity_id = kwargs['entity_id']

        if basic_level == 255:
            direction = 'up'
        elif basic_level == 0:
            direction = 'down'

        if direction:
            self.log('{}: {}'.format(entity_id, direction))