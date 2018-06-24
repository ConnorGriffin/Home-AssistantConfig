import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime

class Ecobee(hass.Hass):

    def initialize(self):
        # Init an empty dict in the global_vars, used for storing various data
        self.global_vars['ecobee'] = {
            'home_status': None
        }

        self.register_constraint('home_status_not')
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

            for climate_mode in self.args.get('climate_modes', {}).get('usually_{}'.format(state),[]):
                # Example: if climate mode changes to away and home status is not away, set a home hold
                self.listen_state(
                    self.ecobee_state_cb,
                    entity = ecobee_entity,
                    attribute = 'climate_mode',
                    new = climate_mode,
                    home_status_not = state
                )
        
        """
        # Listen for ecobee climate mode and hold mode changes
        self.listen_state(
            self.ecobee_state_cb,
            entity = ecobee_entity,
            attribute = 'hold_mode',
        )
        self.listen_state(
            self.ecobee_state_cb,
            entity = ecobee_entity,
            attribute = 'away_mode'
        )
        """

    
    def monitor_ecobee_action(self, kwargs):
        entity = kwargs['entity']
        state = kwargs['state']

        # Evaluate if we need to set a hold (first load)
        if self.home_status_not(state):
            self.log('set a hold')
            # Set a hold? IDK, uncommented so that I wouldn't get an indent error tbh

        # Create a listener (future events)
        self.listen_state(
            self.ecobee_state_cb,
            entity = ecobee_entity,
            attribute = 'climate_mode',
            new = climate_mode,
            home_status_not = state
        )


    # Callback for ecobee state changes
    def ecobee_state_cb(self, entity, attribute, old, new, kwargs):
        presence = kwargs['presence']
        action = kwargs['action']
        self.log([entity, attribute, old, new, presence, action])


    # Inverse constraint, returns true if home status isn't equal to the provided value
    def home_status_not(self, value):
        return value != self.global_vars['ecobee']['home_status']


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
            # Call an ecobee function here that sets home/away based on state and current climate mode


    # Callback for presence changes
    def presence_cb(self, entity, attribute, old, new, kwargs):
        self.log([entity, attribute, old, new])
        duration = kwargs.get('state_duration', 0)
        # Check if the state is still the same after duration (number of seconds)
        self.run_in(
            self.home_status_cb,
            seconds = duration+1,
            entity_id = entity,
            state = new,
            state_duration = duration
        )
