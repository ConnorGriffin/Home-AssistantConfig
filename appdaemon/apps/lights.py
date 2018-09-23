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
                mode_entity = 'input_select.{}_mode'.format(entity_id)
                motion_sensor = entity.get('motion_sensor', None)
                humidity_sensor = entity.get('humidity_sensor', None)
                humidity_threshold = entity.get('humidity_threshold', None)
                on_delay = entity.get('on_delay', self.args['default_on_delay'])
                off_delay = entity.get('off_delay', self.args['default_off_delay'])

                # Initialize the global settings for each entity
                self.global_vars['lights'][light_entity] = {
                    'override':       None,
                    'prev_override':  None,
                    'next_action':    None,
                    'setpoint':       0,
                    'mode':           self.get_state(mode_entity),
                    'max_brightness': entity.get('max_brightness', self.args['default_max_brightness']),
                    'min_brightness': entity.get('min_brightness', self.args['default_min_brightness'])
                }

                # Listen for double taps
                self.log("Monitoring {} for double tap.".format(light_friendly), "INFO")
                self.listen_event(
                    self.double_tap_cb,
                    "zwave.node_event",
                    entity_id = zwave_entity,
                    light_entity = light_entity,
                    constrain_input_boolean = 'input_boolean.light_double_tap_automation'
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

                # Set auto-brightness every 5 minutes if light is on and mode is Automatic
                self.run_every(
                    self.auto_brightness_cb,
                    datetime.datetime.now(),
                    300,
                    entity_id = light_entity,
                    transition = 300,
                    check_current_brightness = True
                )

                # Listen for mode dropdown changes
                self.log("Monitoring {} for mode dropdown changes.".format(light_friendly), "INFO")
                self.listen_state(
                    self.mode_dropdown_cb,
                    entity = mode_entity
                )

                # Presence detection
                if motion_sensor:
                    self.log("Monitoring {} for presence changes.".format(light_friendly), "INFO")
                    self.listen_state(
                        cb = self.presence_cb,
                        entity = motion_sensor,
                        light_entity = light_entity,
                        new = 'on',
                        duration = on_delay,
                        constrain_input_boolean = 'input_boolean.light_presence_automation'
                    )
                    self.listen_state(
                        cb = self.presence_cb,
                        entity = motion_sensor,
                        light_entity = light_entity,
                        new = 'off',
                        duration = off_delay,
                        constrain_input_boolean = 'input_boolean.light_presence_automation'
                    )

                # Humidity detection (keep light on if showering)
                if humidity_sensor and humidity_threshold:
                    self.log("Monitoring {} for humidity threshold of {}%.".format(light_friendly, humidity_threshold), "INFO")
                    self.listen_state(
                        cb = self.humidity_cb,
                        entity = humidity_sensor,
                        light_entity = light_entity,
                        humidity_threshold = humidity_threshold,
                        constrain_input_boolean = 'input_boolean.light_presence_automation'
                    )

                # Set auto-brightness once on startup
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


    def mode_dropdown_cb(self, entity, attribute, old, new, kwargs):
        # TODO: Store mode (automatic/manual) and restore that setting instead of resetting to schedule
        light_entity = entity.replace('input_select','light').replace('_mode','')
        zwave_entity = light_entity.replace('light.', 'zwave.')
        setting = self.global_vars['lights'][light_entity]
        if new == 'Maximum' and setting['override'] != 'Maximum':
            # Set a maximum brightness hold
            self.set_override(
                entity_id = light_entity,
                override = 'Maximum',
                brightness_pct = setting['max_brightness']
            )
        elif new == 'Minimum' and setting['override'] != 'Minimum':
            # Set a minimum brightness hold
            self.set_override(
                entity_id = light_entity,
                override = 'Minimum',
                brightness_pct = setting['min_brightness']
            )
        elif new == 'Automatic':
            # Revert to the automatic brightness when changed to 'Automatic'
            setting['override'] = None
            setting['setpoint'] = 0
            self.auto_brightness_cb(dict(entity_id = light_entity))

        # Refresh the z-wave entity since the light doesn't show as on in the HA UI and setting refresh_value in zwave config breaks too many other things
        #self.run_in(
        #    self.refresh_zwave_entity,
        #    seconds = 1,
        #    entity_id = zwave_entity
        #)


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
        mode_entity = 'input_select.{}_mode'.format(entity_id.split('.')[1])
        # Get the snooze minutes from the setting dict
        for entity in self.args['entities']:
            if entity['name'] == entity_id.split('.')[1]:
                snooze_minutes = entity.get('snooze_minutes', None)

        if setting['override'] == override:
            # Reset if the current action is called again (double tap once turns on, second time resets)
            setting['override'] = None
            # TODO: Set the previous mode here instead of defaulting to Automatic
            self.call_service(
                service = 'input_select/select_option',
                entity_id = mode_entity,
                option = 'Automatic'
            )

            # Run twice, sets an instant brightness, then a slow transition (like if it was never taken off schedule)
            self.auto_brightness_cb(dict(
                entity_id = entity_id,
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
            setting['setpoint'] = 0
            self.turn_on(entity_id, brightness_pct=brightness_pct)
            self.call_service(
                service = 'input_select/select_option',
                entity_id = mode_entity,
                option = override
            )


    def refresh_zwave_entity(self, kwargs):
        entity_id = kwargs.get('entity_id')
        self.call_service(
            service = 'zwave/refresh_entity',
            entity_id = entity_id
        )


    def resume_from_snooze(self, kwargs):
        entity_id = kwargs.get('entity_id')
        setting = self.global_vars['lights'][entity_id]
        setting['override'] = 'alarm'
        setting['setpoint'] = 0
        self.turn_on(entity_id, brightness_pct=setting['max_brightness'])


    def alarm_fired_cb(self, event_name, data, kwargs):
        light_entity = kwargs.get('light_entity')
        zwave_entity = light_entity.replace('light.', 'zwave.')
        hide_switch_groups = kwargs.get('hide_switch_groups')
        alarm_name = data['alarm_name']
        alarm_group = 'group.{}'.format(alarm_name)
        setting = self.global_vars['lights'][light_entity]
        override = setting['override']

        # If the alarm is already triggered, don't do anything
        if override != 'alarm':
            # Turn on the configured light to full brightness
            self.log('{}: Turned on by alarm {}.'.format(self.friendly_name(light_entity), self.friendly_name(alarm_group)))
            self.set_override(
                entity_id = light_entity,
                override = 'alarm',
                brightness_pct = setting['max_brightness']
            )

            # Refresh the z-wave entity since the light doesn't show as on in the HA UI and setting refresh_value in zwave config breaks too many other things
            #self.run_in(
            #    self.refresh_zwave_entity,
            #    seconds = 1,
            #    entity_id = zwave_entity
            #)

            # Hide the switch from the specified groups when the alarm is triggered
            for group in hide_switch_groups:
                group_id = 'group.{}'.format(group)
                entities = self.get_state(group_id, attribute='entity_id')

                self.log('Hiding {} from {}.'.format(self.friendly_name(light_entity), self.friendly_name(group_id)))

                # Copy the list of entities in the group now, then remove the light switch
                original_entities = entities.copy()
                entities.remove(light_entity)

                # TODO: Set mode dropdown options to just 'Alarm' while alarm is enabled
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
        setting = self.global_vars['lights'][light_entity]

        if basic_level in [255,0]:
            if basic_level == 255:
                direction = 'up'
                override = 'Maximum'
                brightness_pct = setting['max_brightness']
            elif basic_level == 0:
                direction = 'down'
                override = 'Minimum'
                brightness_pct = setting['min_brightness']

            self.set_override(light_entity, override, brightness_pct)

            light_friendly = self.friendly_name(light_entity)
            self.log('{}: Double tapped {}'.format(light_friendly, direction))


    # Nullify the override when a light is turned off
    def turned_off_cb(self, entity, attribute, old, new, kwargs):
        # TODO: Either reset the dropdown to 'Automatic' here, or implement persistent state/settings
        setting = self.global_vars['lights'][entity]
        setting['override'] = None
        setting['prev_override'] = None
        setting['next_action'] = None
        setting['setpoint'] = 0
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
        if self.get_state('input_boolean.light_brightness_automation') == 'off':
            return None

        entity_id = kwargs.get('entity_id')
        immediate = kwargs.get('immediate')
        source = kwargs.get('source', None)
        transition = kwargs.get('transition', 0)
        check_current_brightness = kwargs.get('check_current_brightness', False)

        friendly_name = self.friendly_name(entity_id)
        state = self.get_state(entity_id)
        setting = self.global_vars['lights'][entity_id]
        mode_entity = 'input_select.{}_mode'.format(entity_id.split('.')[1])
        max_brightness = setting['max_brightness']
        min_brightness = setting['min_brightness']
        now = datetime.datetime.now()

        if check_current_brightness:
            current_brightness = self.get_state(entity_id, attribute='brightness')
            if not current_brightness:
                current_brightness = 0
            current_brightness_pct = current_brightness / 2.55

        # Set auto-brightness if light is on and no override exists
        # state flip-flops when light is first turned on, use the source to ignore state
        if (state == 'on' or source in ['turned_on_cb', 'set_override', 'presence']) and not setting['override']:
            # Get the brightness schedule from the setting dict
            for entity in self.args['entities']:
                if entity['name'] == entity_id.split('.')[1]:
                    schedule = entity.get('brightness_schedule', self.args['default_brightness_schedule'])

            # Iterate for each item in the schedule, set i = item index, determine the brightness to use
            for i in range(len(schedule)):
                # Get the next schedule item, go to 0 (wrap around) if we're on the last schedule
                if i+1 == len(schedule):
                    next_schedule = schedule[0]
                else:
                    next_schedule = schedule[i+1]

                # Replace strings max/min_brightness with percents
                if next_schedule['pct'] == 'max_brightness':
                    next_schedule_pct = max_brightness
                elif next_schedule['pct'] == 'min_brightness':
                    next_schedule_pct = min_brightness
                else:
                    next_schedule_pct = next_schedule['pct']

                if schedule[i]['pct'] == 'max_brightness':
                    this_schedule_pct = max_brightness
                elif schedule[i]['pct'] == 'min_brightness':
                    this_schedule_pct = min_brightness
                else:
                    this_schedule_pct = schedule[i]['pct']

                # Determine if now is during or between two schedules
                in_schedule = self.timestr_delta(schedule[i]['start'], now, schedule[i]['end'])
                between_schedule = self.timestr_delta(schedule[i]['end'], now, next_schedule['start'])

                if in_schedule['now_is_between']:
                    # If we're within a schedule entry's time window, match exactly
                    target_percent = this_schedule_pct
                    transition = 0

                    # don't eval any ore schedules
                    break
                elif between_schedule['now_is_between']:
                    # if we are between two schedules, calculate the brightness percentage
                    time_diff = between_schedule['start_to_end'].total_seconds()
                    bright_diff = this_schedule_pct - next_schedule_pct
                    bright_per_second = bright_diff / time_diff

                    if immediate:
                        # If setting an immediate brightness, we want to calculate the brightness percentage and then make a recursive call
                        target_percent = this_schedule_pct - (between_schedule['since_start'].total_seconds() * bright_per_second)
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
                            target_percent = next_schedule_pct
                            transition = between_schedule['to_end'].total_seconds()
                        else:
                            target_percent = this_schedule_pct - ((between_schedule['since_start'].total_seconds() + transition) * bright_per_second)

                    # don't eval any more schedules
                    break

            # set brightness if a schedule was matched and the percent has changed since the last auto-brightness run
            # Don't change if the brightness was changed from another source (at the switch, hass ui, google assistant, etc.)
            if target_percent:
                last_percent = setting.get('setpoint')
                if last_percent != target_percent:
                    if check_current_brightness and abs(last_percent - current_brightness_pct) > 3:
                        self.log('{}: Brightness changed manually, not moving'.format(friendly_name))
                        self.call_service(
                            service = 'input_select/select_option',
                            entity_id = mode_entity,
                            option = 'Manual'
                        )

                    else:
                        self.log("{}: Setting auto-brightness - {}% over {} seconds".format(friendly_name, round(target_percent, 2), transition))
                        self.turn_on(
                            entity_id,
                            brightness_pct = target_percent,
                            transition = transition
                        )
                        setting['setpoint'] = target_percent


    def presence_cb(self, entity, attribute, old, new, kwargs):
        light_entity = kwargs.get('light_entity')
        light_friendly = self.friendly_name(light_entity)
        light_state = self.get_state(light_entity)
        setting = self.global_vars['lights'][light_entity]

        # Testing only: only use motion-activated lighting if Diana isn't home
        #if self.get_state('device_tracker.diana_pixel2') == 'not_home':
        #    self.log('{}: No action taken, Diana is home.'.format(light_friendly))
        #else:
        # Turn on light if it's off and presence is detected (and vice-versa)
        if new == 'on' and light_state == 'off':
            # If light is off, turn on with auto_brightness unless auto brightness is disabled
            if self.get_state('input_boolean.light_brightness_automation') == 'on':
                self.auto_brightness_cb(dict(entity_id=light_entity, source='presence'))
            else:
                self.turn_on(light_entity)
            self.log('{}: Turning on, presence detected.'.format(light_friendly))
        elif new == 'off' and light_state == 'on':
            if setting['override'] == 'showering':
                setting['next_action'] = 'turn_off'
                self.log('{}: Turning off when humidity drops below threshold.'.format(light_friendly))
            else:
                self.turn_off(light_entity)
                self.log('{}: Turning off, no presence detected.'.format(light_friendly))
        elif new == 'on' and light_state == 'on' and setting['override'] == 'showering' and setting['next_action'] == 'turn_off':
            setting['next_action'] = None
            self.log('{}: Cancelling next action (humidity turn off), presence detected.'.format(light_friendly))

    # Keep the lights on if someone is showering
    def humidity_cb(self, entity, attribute, old, new, kwargs):
        light_entity = kwargs.get('light_entity')
        humidity_threshold = kwargs.get('humidity_threshold')
        light_friendly = self.friendly_name(light_entity)
        light_state = self.get_state(light_entity)
        setting = self.global_vars['lights'][light_entity]

        # When we've started showering store the previous override, set the current override to 'showering', and turn on the lights
        # When we're done showering revert to the previous override setting
        if float(new) >= humidity_threshold and setting['override'] != 'showering':
            setting['prev_override'] = setting['override']
            setting['override'] = 'showering'
            if light_state == 'off':
                # If light is off, turn on with auto_brightness unless auto brightness is disabled
                if self.get_state('input_boolean.light_brightness_automation') == 'on':
                    self.auto_brightness_cb(dict(entity_id=light_entity, source='presence'))
                else:
                    self.turn_on(light_entity)
            self.log('{}: Shower is running, turning on lights and ignoring motion detection.'.format(light_friendly))
        elif float(new) < humidity_threshold and setting['override'] == 'showering':
            setting['override'] = setting['prev_override']
            setting['prev_override'] = 'showering'
            self.log('{}: Shower is no longer running, resuming motion detection.'.format(light_friendly))
            if setting['next_action'] == 'turn_off':
                self.turn_off(light_entity)
                self.log('{}: Turning off, no presence detected.'.format(light_friendly))