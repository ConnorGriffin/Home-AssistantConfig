import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime

class Ecobee(hass.Hass):

    def initialize(self):
        # Init an empty dict in the global_vars, used for storing various data
        self.global_vars['ecobee'] = {
            'home_status': None
        }

        ecobee_entity = self.args['ecobee_entity']
        presence_entity = self.args['presence_entity']
        
        for state in ['home', 'not_home']:
            # Set home_status global var on init, then setup listeners to keep it updated
            duration = self.args['{}_delay'.format(state)]
            self.home_status_cb(dict(
                entity_id = presence_entity,
                state = state,
                state_duration = duration
            ))
            self.listen_state(
                self.presence_cb,
                entity_id = self.args['presence_entity'],
                new = state,
                state_duration = duration
            )

        # Listen for any ecobee state changes
        self.listen_state(
            self.ecobee_state_cb,
            entity = ecobee_entity,
        )
        
        # Re-check state when the automation is re-enabled
        self.listen_state(
            self.ecobee_state_cb,
            entity_id = self.args['constraint_input_boolean'],
            new = 'on'
        )

    
    def ecobee_action_cb(self):
        if (self.get_state(self.args['constraint_input_boolean']) == 'on'):
            home_modes = self.args.get('climate_modes', {}).get('usually_home',[])
            away_modes = self.args.get('climate_modes', {}).get('usuaully_not_home',[])
            ecobee_entity = self.args['ecobee_entity']
            state_data = self.get_state(ecobee_entity, attribute='all')
            home = self.global_vars['ecobee']['home_status'] == 'home'
            away_hold = state_data['attributes']['away_mode']
            hold_mode = state_data['attributes']['hold_mode']
            climate_mode = state_data['attributes']['climate_mode']

            # For some reason away holds set away_hold and not hold_mode, handle this
            if not hold_mode and away_hold == "on":
                hold_mode = "away"
            
            # This is so we don't cancel temp or vacation holds
            if home:
                hold_match = hold_mode in ['away', 'home'] or not hold_mode
            else:
                hold_match = hold_mode in ['away', 'home', 'temp'] or not hold_mode

            # Don't run if the ecobee is off
            if hold_match and state_data['attributes']['operation_mode'] != 'off':
                if home:
                    if hold_mode != 'home' and climate_mode in away_modes:
                        # Home during a standard away time, set a home hold
                        self.log('Setting a home hold.')
                        self.call_service(
                            service = 'climate/set_hold_mode',
                            entity_id = ecobee_entity,
                            hold_mode = 'home'
                        )
                    elif hold_mode and climate_mode in home_modes:
                        # Home during a hold and comfort setting is a home setting
                        self.log('Resuming action (home).')
                        self.call_service(
                            service = 'climate/ecobee_resume_program',
                            entity_id = ecobee_entity,
                            resume_all = True
                        )
                elif not home:
                    if hold_mode != 'away' and climate_mode in home_modes:
                        # Comfort mode isn't away and we aren't in a home hold
                        self.log('Setting an away hold.')
                        self.call_service(
                            service = 'climate/set_hold_mode',
                            entity_id = ecobee_entity,
                            hold_mode = 'away'
                        )
                    elif hold_mode and climate_mode in away_modes:
                        # Away during a hold and comfort setting is an away setting
                        self.log('Resuming action (away).')
                        self.call_service(
                            service = 'climate/ecobee_resume_program',
                            entity_id = ecobee_entity,
                            resume_all = True
                        )


    # Callback for ecobee state changes
    def ecobee_state_cb(self, entity, attribute, old, new, kwargs):
        self.ecobee_action_cb()


    # Check if state has existed for an arbitrary duration in seconds
    def home_status_cb(self, kwargs):
        # Can't use named parameters because I'm using this as a callback
        entity = kwargs['entity_id']
        state = kwargs['state']
        duration = kwargs['state_duration']

        now = datetime.utcnow()
        state_data = self.get_state(entity, attribute='all')
        #self.log(state_data)
        last_changed = self.convert_utc(state_data['last_changed'])
        last_changed = last_changed.replace(tzinfo=None)
        duration = (now - last_changed).total_seconds() >= duration

         # Update global vars home_status if state has matched state argument for duration number of seconds
        if duration and state_data['state'] == state:
            self.global_vars['ecobee']['home_status'] = state
            self.ecobee_action_cb()


    # Callback for presence changes
    def presence_cb(self, entity, attribute, old, new, kwargs):
        duration = kwargs.get('state_duration', 0)
        # Check if the state is still the same after duration (number of seconds)
        self.run_in(
            self.home_status_cb,
            seconds = duration+1,
            entity_id = entity,
            state = new,
            state_duration = duration
        )
