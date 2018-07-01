import appdaemon.plugins.hass.hassapi as hass
import datetime

class Lights(hass.Hass):

    def initialize(self):
        # Init an empty dict in the global_vars, used for storing data in various lights apps
        self.global_vars['lights'] = {}

        if "entities" in self.args:
            # Loop through the entities 
            for entity in self.args["entities"]:
                # Get the entity settings
                entity_id = entity['name']
                alarms = entity.get('alarms',{})

                # Convert entity name into useable entity_ids
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
                    entity_id = zwave_entity, 
                    light_entity = light_entity
                )

                # Listen for light getting turned off
                self.log("Monitoring {} for turn off.".format(light_friendly), "INFO")
                self.listen_state(
                    self.turned_off_cb,
                    entity = light_entity,
                    new = 'off',
                    old = 'on'
                )

                # Listen for light getting turned on
                self.log("Monitoring {} for turn on.".format(light_friendly), "INFO")
                self.listen_state(
                    self.turned_on_cb,
                    entity = light_entity,
                    new = 'on',
                    old = 'off'
                )

                # Set auto-brightness every 5 minutes if light is on
                self.run_every(
                    self.auto_brightness_cb,
                    datetime.datetime.now(),
                    300,
                    entity_id = light_entity,
                    transition = 300
                )

                # Set auto-brightness every 5 minutes if light is on
                self.auto_brightness_cb(dict(entity_id = light_entity))

                # Iterate over each alarm setting in each light 
                for alarm in alarms:
                    hide_switch_groups = alarm.get('hide_switch_from_groups',[])

                    # Setup a listener for each alarm name in the group
                    for alarm_name in alarm.get('alarm_groups',[]): 
                        self.log('Monitoring {} for {}.'.format(light_friendly, alarm_name))
                        self.listen_event(
                            self.alarm_fired_cb,
                            'alarm_fired',
                            alarm_name = alarm_name,
                            light_entity = light_entity,
                            hide_switch_groups = hide_switch_groups
                        )

                        
    def timestr_delta(self, start_time_str, now, end_time_str, name=None):
        start_time = self.parse_time(start_time_str, name)
        end_time = self.parse_time(end_time_str, name)
        
        start_date = now.replace(
            hour=start_time.hour, minute=start_time.minute,
            second=start_time.second
        )
        end_date = now.replace(
            hour=end_time.hour, minute=end_time.minute, second=end_time.second
        )
        if end_date < start_date:
            # Spans midnight
            if now < start_date and now < end_date:
                now = now + datetime.timedelta(days=1)
            end_date = end_date + datetime.timedelta(days=1)
        return {
            "now_is_between": (start_date <= now <= end_date),
            "start_to_end": (end_date - start_date),
            "since_start": (now - start_date),
            "to_end": (end_date - now),
            "start_date": start_date,
            "end_date": end_date
        }


    def restore_group_cb(self, entity, attribute, old, new, kwargs):
        group = kwargs.get('group')
        original_entities = kwargs.get('original_entities') 

        # Update the group with the new entity list (remove the light switch)
        self.log('Resetting {} entities (unhiding light).'.format(self.friendly_name('group.{}'.format(group))))
        self.call_service(
            service = 'group/set',
            object_id = group,
            entities = original_entities
        )

        # Stop the listener manually, can't use a oneshot until https://github.com/home-assistant/appdaemon/pull/299 is merged
        self.cancel_listen_event(kwargs['handle'])
        

    # Used by other functions to set overrides and store override data in the global_vars dictionary
    def set_override(self, entity_id, override, brightness_pct):
        setting = self.global_vars['lights'][entity_id]
        # Get the snooze minutes from the setting dict
        for entity in self.args['entities']:
            if entity['name'] == entity_id.split('.')[1]:
                snooze_minutes = entity['snooze_minutes']

        if setting['override'] == override:
            # Reset if the current action is called again (double tap once turns on, second time resets)
            setting['override'] = None

            # Run twice, sets an instant brightness, then a slow transition (like if it was never taken off schedule)
            self.auto_brightness_cb(dict(
                entity_id=entity_id,
                immediate = True,
                source = 'set_override'
            ))
        elif setting['override'] == 'alarm' and override != 'alarm' and snooze_minutes:
            # If the current override is alarm and snooze is configured
            self.turn_off(entity_id)
            self.run_in(
                self.resume_from_snooze,
                seconds = snooze_minutes * 60,
                entity_id = entity_id
            )
        else: 
            setting['override'] = override
            setting['setpoint'] = None
            self.turn_on(entity_id, brightness=brightness_pct*2.55)


    def resume_from_snooze(self, kwargs):
        entity_id = kwargs.get('entity_id')
        setting = self.global_vars['lights'][entity_id]
        setting['override'] = 'alarm'
        setting['setpoint'] = None
        self.turn_on(entity_id, brightness=255)


    def alarm_fired_cb(self, event_name, data, kwargs):
        light_entity = kwargs.get('light_entity')
        hide_switch_groups = kwargs.get('hide_switch_groups')
        alarm_name = data['alarm_name']
        alarm_group = 'group.{}'.format(alarm_name)
        override = self.global_vars['lights'][light_entity]['override']

        # If the alarm is already triggered, don't do anything
        if override != 'alarm':
            # Turn on the configured light to full brightness
            self.log('{}: Turned on by alarm {}.'.format(self.friendly_name(light_entity), self.friendly_name(alarm_group)))
            self.set_override(
                entity_id = light_entity,
                override = 'alarm',
                brightness_pct = 100
            )

            # Hide the switch from the specified groups when the alarm is triggered
            for group in hide_switch_groups:
                group_id = 'group.{}'.format(group)
                entities = self.get_state(group_id, attribute='entity_id')

                self.log('Hiding {} from {}.'.format(self.friendly_name(light_entity), self.friendly_name(group_id)))

                # Copy the list of entities in the group now, then remove the light switch
                original_entities = entities.copy()
                entities.remove(light_entity)

                # Update the group with the new entity list (remove the light switch)
                self.call_service(
                    service = 'group/set',
                    object_id = group,
                    entities = entities
                )

                # Setup a listener that will restore the original entity list when the light is interacted with in any way
                # Can't use oneshot beause of a bug. Waiting for this to be merged: https://github.com/home-assistant/appdaemon/pull/299
                self.listen_state(
                    self.restore_group_cb,
                    entity = light_entity,
                    old = 'on',
                    new = 'off',
                    original_entities = original_entities,
                    group = group
                )


    # Set max/min brightness on double tap up/down
    def double_tap_cb(self, event_name, data, kwargs):
        basic_level = data["basic_level"]
        light_entity = kwargs['light_entity']
 
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
            
            light_friendly = self.friendly_name(light_entity)
            self.log('{}: Double tapped {}'.format(light_friendly, direction))
    

    # Nullify the override when a light is turned off
    def turned_off_cb(self, entity, attribute, old, new, kwargs):
        self.global_vars['lights'][entity]['override'] = None
        self.global_vars['lights'][entity]['setpoint'] = None
        self.set_state(entity, state = 'off', attributes = {"brightness": 0})

        light_friendly = self.friendly_name(entity)
        self.log('{}: Turned off'.format(light_friendly))


    # Call auto_brightness_cb when a light is turned on 
    def turned_on_cb(self, entity, attribute, old, new, kwargs):
        light_friendly = self.friendly_name(entity)
        self.log('{}: Turned on'.format(light_friendly))

        # Run twice, sets an instant brightness, then a slow transition (like if it was never taken off schedule)
        self.auto_brightness_cb(dict(
            entity_id=entity, 
            source='turned_on_cb',
            immediate = True
        ))
        
        
    # Set brightness automatically based on schedule
    def auto_brightness_cb(self, kwargs):
        entity_id = kwargs.get('entity_id')
        immediate = kwargs.get('immediate')
        source = kwargs.get('source', None)
        transition = kwargs.get('transition', 0)

        friendly_name = self.friendly_name(entity_id)
        state = self.get_state(entity_id)
        setting = self.global_vars['lights'][entity_id]
        now = datetime.datetime.now()

        # Set auto-brightness if light is on and no override exists
        # state flip-flops when light is first turned on, use the source to ignore state
        if (state == 'on' or source in ['turned_on_cb', 'set_override']) and not setting['override']:
            schedule = self.app_config['lights']['brightness_schedule']

            # Iterate for each item in the schedule, set i = item index, determine the brightness to use
            for i in range(len(schedule)):
                # Get the next schedule item, go to 0 (wrap around) if we're on the last schedule
                if i+1 == len(schedule):
                    next_schedule = schedule[0]
                else:
                    next_schedule = schedule[i+1]

                # Determine if now is during or between two schedules
                in_schedule = self.timestr_delta(schedule[i]['start'], now, schedule[i]['end'])
                between_schedule = self.timestr_delta(schedule[i]['end'], now, next_schedule['start'])

                if in_schedule['now_is_between']:
                    # If we're within a schedule entry's time window, match exactly
                    target_percent = schedule[i]['pct']
                    transition = 0

                    # don't eval any ore schedules
                    break 
                elif between_schedule['now_is_between']:
                    # if we are between two schedules, calculate the brightness percentage
                    time_diff = between_schedule['start_to_end'].total_seconds()
                    bright_diff = schedule[i]['pct'] - next_schedule['pct']
                    bright_per_second = bright_diff / time_diff 
                    
                    if immediate:
                        # If setting an immediate brightness, we want to calculate the brightness percentage and then make a recursive call
                        target_percent = schedule[i]['pct'] - (between_schedule['since_start'].total_seconds() * bright_per_second)
                        transition = 0
                        self.run_in(
                            self.auto_brightness_cb,
                            seconds = 5,
                            entity_id = entity_id,
                            transition = 295
                        )
                    else:
                        if between_schedule['to_end'].total_seconds() <= transition:
                            # If we're in a new schedule in the next 5 minutes, use that schedule's brightness
                            target_percent = next_schedule['pct']
                            transition = between_schedule['to_end'].total_seconds()
                        else:
                            target_percent = schedule[i]['pct'] - ((between_schedule['since_start'].total_seconds() + transition) * bright_per_second)
                    
                    # don't eval any ore schedules 
                    break 

            # set brightness if a schedule was matched and the percent has changed since the last auto-brightness run
            if target_percent:
                last_percent = setting.get('setpoint')
                if last_percent != target_percent:
                    self.log("{}: Setting auto-brightness - {}% over {} seconds".format(friendly_name, round(target_percent, 2), transition))
                    self.turn_on(
                        entity_id,
                        brightness = target_percent * 2.55, 
                        transition = transition
                    )
                    setting['setpoint'] = target_percent
