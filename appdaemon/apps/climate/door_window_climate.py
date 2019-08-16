# TODO: Add temperature delta dependent rules
# TODO: Add notifications for when the AC is turned on/off by the app, maybe incorporeate actionable notifications (windows open, do you want to turn off AC?)

import appdaemon.plugins.hass.hassapi as hass

class DoorWindowClimate(hass.Hass):

    def initialize(self):
        rules = self.args.get('climate_rules', [])

        # We'll put data in these later
        self.rule_data = {}
        self.rule_counts = {
            'active_rules': [],
            'inactive_rules': [],
            'total_rules': len(rules)
        }
        self.climate_data = {
            'last_mode': None,
            'current_mode': self.get_state(self.args.get('climate'), attribute='hvac_action')
        }

        # Figure out if each rule is open or closed based on a combination of zones and sensors
        for rule in rules:
            dependencies = rule.get('dependencies', [])

            # Pull in the settings for each rule, otherwise use the default settings
            door_open_seconds = rule.get('door_open_seconds', self.args['door_open_seconds'])
            door_closed_seconds = rule.get('door_closed_seconds', self.args['door_closed_seconds'])

            # Setup a persistent data store for each rule
            self.rule_data[rule['name']] = {
                'state': None,
                'open_sensors': [],
                'closed_sensors': [],
                'total_sensors': len(dependencies)
            }

            # Determine the dependency type and setup listeners
            for dependency in dependencies:
                if dependency.get('zone'):
                    entity = dependency['zone']

                    # Get the initial state (so stuff works if AppDaemon reboots)
                    self.run_in(
                        self.eval_rule,
                        seconds = 5,
                        rule = rule,
                        entity_id = entity
                    )

                    # Listen for state changes
                    self.listen_state(
                        cb = self.dependency_cb,
                        entity = entity,
                        rule = rule
                    )
                elif dependency.get('door'):
                    entity = dependency['door']
                    self.listen_state(
                        cb = self.dependency_cb,
                        entity = entity,
                        new = 'off',
                        duration = door_closed_seconds,
                        immediate = True,
                        rule = rule
                    )
                    self.listen_state(
                        cb = self.dependency_cb,
                        entity = entity,
                        new = 'on',
                        duration = door_open_seconds,
                        immediate = True,
                        rule = rule
                    )

    def dependency_cb(self, entity, attribute, old, new, kwargs):
        eval_kwargs = {
            'entity_id': entity,
            'rule': kwargs.get('rule')
        }
        self.eval_rule(eval_kwargs)


    def eval_rule(self, kwargs):
        """ Handles sensor state in the context of a rule, determines if the rule is
        active or not as a result, and takes action based on the state of other rules. """

        entity = kwargs.get('entity_id')
        rule = kwargs.get('rule')
        state = self.get_state(entity).lower()
        rule_name = rule['name']
        mode = rule['mode']
        closed_sensors = self.rule_data[rule_name].get('closed_sensors', [])
        open_sensors = self.rule_data[rule_name].get('open_sensors', [])
        current_state = self.rule_data[rule_name]['state']
        climate = self.args.get('climate')
        new_state = None

        # Add/remove the sensor from the closed_sensors or open_sensors list
        if state in ['closed', 'off']:
            if entity not in closed_sensors:
                self.rule_data[rule_name]['closed_sensors'].append(entity)
            if entity in open_sensors:
                self.rule_data[rule_name]['open_sensors'].remove(entity)
        elif state in ['open', 'on']:
            if entity not in open_sensors:
                self.rule_data[rule_name]['open_sensors'].append(entity)
            if entity in closed_sensors:
                self.rule_data[rule_name]['closed_sensors'].remove(entity)

        # Get the open/closed count after manipulating the lists
        open_count = len(self.rule_data[rule_name]['open_sensors'])
        closed_count = len(self.rule_data[rule_name]['closed_sensors'])

        # Set rule state once all sensors are accounted for
        if (open_count + closed_count) == self.rule_data[rule_name]['total_sensors']:
            if mode == 'any':
                if open_count >= 1:
                    new_state = 'active'
                else:
                    new_state = 'inactive'
            elif mode == 'all':
                if closed_count >= 1:
                    new_state = 'inactive'
                else:
                    new_state = 'active'

            # Get the rule statuses
            active_rules = self.rule_counts['active_rules']
            inactive_rules = self.rule_counts['inactive_rules']

            # Add/remove the rule from the active/inactive lists
            if new_state == 'inactive':
                if rule_name not in inactive_rules:
                    self.rule_counts['inactive_rules'].append(rule_name)
                if rule_name in active_rules:
                    self.rule_counts['active_rules'].remove(rule_name)
            elif new_state == 'active':
                if rule_name not in active_rules:
                    self.rule_counts['active_rules'].append(rule_name)
                if rule_name in inactive_rules:
                    self.rule_counts['inactive_rules'].remove(rule_name)

            # Take action based on rule state changes
            if new_state == 'active' and new_state != current_state:
                # Store the new state and climate data
                self.rule_data[rule_name]['state'] = new_state

                # Only make changes if this is the first rule to fire (rules are 'any' not 'all')
                if len(self.rule_counts['active_rules']) == 1:
                    self.log('{} (rule) is {}, turning off AC.'.format(rule_name, new_state))

                    self.climate_data['last_mode'] = self.get_state(climate, attribute='hvac_action')
                    self.climate_data['current_mode'] = 'off'

                    # Set the AC mode
                    self.call_service(
                        service = 'climate/set_hvac_mode',
                        entity_id = climate,
                        hvac_mode = 'off'
                    )

                    # Set the automation status sensor
                    self.set_state(
                        entity_id = 'binary_sensor.door_window_climate_control_active',
                        state = 'on',
                        attributes = {
                            'friendly_name': 'Door/Window Climate Control',
                            'icon': 'mdi:thermostat'
                        }
                    )

                else:
                    self.log('{} (rule) is {}, but another rule is active. Doing nothing.'.format(rule_name, new_state))
            elif new_state == 'inactive' and new_state != current_state:
                # Store the rule state
                self.rule_data[rule_name]['state'] = new_state

                # Only make changes if this is the last rule to turn off
                if len(self.rule_counts['active_rules']) == 0:
                    # Set the automation status sensor
                    self.set_state(
                        entity_id = 'binary_sensor.door_window_climate_control_active',
                        state = 'off',
                        attributes = {
                            'friendly_name': 'Door/Window Climate Control',
                            'icon': 'mdi:thermostat'
                        }
                    )

                    # Change AC back to the previous mode, but only if it hasn't been manually changed since it was turned off
                    climate_mode = self.get_state(climate, attribute='hvac_action')
                    if climate_mode == self.climate_data['current_mode'] and self.climate_data['last_mode']:
                        new_mode = self.climate_data['last_mode']
                        self.log('{} (rule) is {}, setting AC back to {}.'.format(rule_name, new_state, new_mode))
                        self.call_service(
                            service = 'climate/set_hvac_mode',
                            entity_id = climate,
                            hvac_mode = new_mode
                        )
                        self.climate_data['last_mode'] = climate_mode,
                        self.climate_data['current_mode'] = new_mode
                    elif self.climate_data['last_mode']:
                        # Log why no action was taken if last_mode isn't None
                        self.log('{} (rule) is {}, but AC has been modified since being turned off. Doing nothing.'.format(rule_name, new_state))
                else:
                    # Log why no action was taken
                    self.log('{} (rule) is {}, but another rule is active. Doing nothing.'.format(rule_name, new_state))