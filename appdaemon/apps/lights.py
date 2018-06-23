import appdaemon.plugins.hass.hassapi as hass
import datetime

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

                # Initialize the global settings for each entity
                self.global_vars['lights'][light_entity] = {
                    'override': None,
                    'setpoint': None
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
                    new='on',
                    old='off'
                )

                # Set auto-brightness every 5 minutes if light is on
                self.run_every(
                    self.auto_brightness_cb,
                    datetime.datetime.now(),
                    300,
                    entity_id=light_entity,
                    transition=300
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
            setting['setpoint'] = None
            self.turn_on(entity_id, brightness_pct=brightness_pct)

    # Set max/min brightness on double tap up/down
    def double_tap_cb(self, event_name, data, kwargs):
        basic_level = data["basic_level"]
        light_entity = kwargs['light_entity']
        light_friendly = self.friendly_name(light_entity)

        if basic_level in [255,0]:
            if basic_level == 255:
                direction = 'up'
                override = 'max_bright'
                brightness_pct = 100
            elif basic_level == 0:
                direction = 'down'
                override = 'min_bright'
                brightness_pct = 10
            
            self.set_override(light_entity, override, brightness_pct)
            self.log('{}: Double tapped {}'.format(light_friendly, direction))
    
    # Nullify the override when a light is turned off
    def turned_off_cb(self, entity, attribute, old, new, kwargs):
        light_friendly = self.friendly_name(entity)
        self.log('{}: Turned off'.format(light_friendly))
        self.global_vars['lights'][entity]['override'] = None
        self.global_vars['lights'][entity]['setpoint'] = None
    
    # Call auto_brightness_cb when a light is turned on 
    def turned_on_cb(self, entity, attribute, old, new, kwargs):
        light_friendly = self.friendly_name(entity)
        self.log('{}: Turned on'.format(light_friendly))
        self.auto_brightness_cb(dict(entity_id=entity, source='turned_on_cb'))
        
    # Set brightness automatically based on schedule
    def auto_brightness_cb(self, kwargs):
        entity_id = kwargs.get('entity_id')
        transition = kwargs.get('transition', 0)
        source = kwargs.get('source', None)

        friendly_name = self.friendly_name(entity_id)
        state = self.get_state(entity_id)
        setting = self.global_vars['lights'][entity_id]

        # Set auto-brightness if light is on and no override exists
        # state flip-flops when light is first turned on, use the source and last_changed_ms to ignore state
        if (state == 'on' or source == 'turned_on_cb') and not setting['override']:
            schedule = self.app_config['lights']['brightness_schedule']
            now = datetime.datetime.now()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            now_minutes = (now - midnight).seconds / 60

            # Iterate for each item in the schedule, set i = item index, determine the brightness to use
            for i in range(len(schedule)):
                current_minutes = now_minutes
                start_minutes = int(schedule[i]['start'].split(':')[0]) * 60 + int(schedule[i]['start'].split(':')[1])
                end_minutes = int(schedule[i]['end'].split(':')[0]) * 60 + int(schedule[i]['end'].split(':')[1])

                # Get the next schedule item, go to 0 (wrap around) if we're on the last schedule
                if i+1 == len(schedule):
                    next_schedule = schedule[0]
                else:
                    next_schedule = schedule[i+1]

                # Get the minutes for the next schedule start time
                next_start_minutes = int(next_schedule['start'].split(':')[0]) * 60 + int(next_schedule['start'].split(':')[1])

                # If schedule ends tomorrow: (4:00 becomes 28:00)
                if end_minutes < start_minutes:
                    end_minutes += 1440
                
                # If the next schedule starts tomorrow (4:00 becomes 28:00)
                if next_start_minutes < end_minutes or end_minutes < start_minutes:
                    next_start_minutes += 1440
                    if end_minutes > start_minutes and current_minutes < start_minutes:
                        current_minutes += 1440  

                if current_minutes >= start_minutes and current_minutes <= end_minutes:
                    # If we're within a schedule entry's time window, match exactly
                    target_percent = schedule[i]['pct']
                    break # don't eval any ore schedules
                elif current_minutes >= end_minutes and current_minutes < next_start_minutes:
                    # if we are between two schedules, calculate the brightness percentage
                    time_diff = next_start_minutes - end_minutes
                    bright_diff = schedule[i]['pct'] - next_schedule['pct']
                    bright_per_minute = bright_diff / time_diff 
                    target_percent = schedule[i]['pct'] - (time_diff - (time_diff - (current_minutes - end_minutes))) * bright_per_minute
                    break # don't eval any ore schedules
             
            # set brightness if a schedule was matched and the percent has changed since the last auto-brightness run
            if target_percent:
                last_percent = setting.get('setpoint')
                if last_percent != target_percent:
                    self.log("{}: Setting auto-brightness - {}%".format(friendly_name, round(target_percent, 2)))
                    self.turn_on(entity_id, brightness_pct=target_percent, transition=transition)
                    setting['setpoint'] = target_percent
