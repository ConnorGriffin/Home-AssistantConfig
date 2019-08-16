# Ecobee auto home/away based on presence.

import appdaemon.plugins.hass.hassapi as hass

class Ecobee(hass.Hass):

    def initialize(self):
        # Init an empty dict in the global_vars, used for storing various data
        self.global_vars['ecobee'] = {
            'home_status': None
        }

        constrain_input_boolean = self.args['constrain_boolean']

        for state in ['home', 'not_home']:
            # Setup a listener for each home state with custom durations - 'immediate = True' makes these eval on first load
            self.listen_state(
                self.presence_cb,
                entity = self.args['presence_entity'],
                new = state,
                immediate = True,
                duration = self.args['{}_delay'.format(state)]
            )

        # Listen for any ecobee state changes
        self.listen_state(
            self.ecobee_state_cb,
            entity = self.args['ecobee_entity'],
            constrain_input_boolean = constrain_input_boolean
        )

        # Re-check state when the automation is re-enabled
        self.listen_state(
            self.constrain_boolean_cb,
            entity = constrain_input_boolean
        )


    # Evaluates ecobee state and determines a hold/resume action
    def ecobee_actions(self):
        # Get config data
        home_modes = self.args.get('climate_modes', {}).get('usually_home',[])
        away_modes = self.args.get('climate_modes', {}).get('usuaully_not_home',[])
        ecobee_entity = self.args['ecobee_entity']
        home = self.global_vars['ecobee']['home_status'] == 'home'

        # Get ecobee state data
        state_data = self.get_state(ecobee_entity, attribute='all')
        preset_mode = state_data['attributes']['preset_mode']
        climate_mode = state_data['attributes']['climate_mode']

        # This is so we don't cancel temp or vacation holds
        if home:
            preset_match = preset_mode in ['away', 'home'] or not preset_mode
        else:
            preset_match = preset_mode in ['away', 'home', 'temp'] or not preset_mode

        # Don't run if the ecobee is off
        if preset_match and state_data['attributes']['hvac_action'] != 'off':
            if home:
                if preset_mode != 'home' and climate_mode in away_modes:
                    # Home during a standard away time, set a home hold
                    self.log('Setting a home hold.')
                    self.call_service(
                        service = 'climate/set_preset_mode',
                        entity_id = ecobee_entity,
                        preset_mode = 'home'
                    )
                elif preset_mode and climate_mode in home_modes:
                    # Home during a hold and comfort setting is a home setting
                    self.log('Resuming action (home).')
                    self.call_service(
                        service = 'climate/ecobee_resume_program',
                        entity_id = ecobee_entity,
                        resume_all = True
                    )
            elif not home:
                if preset_mode != 'away' and climate_mode in home_modes:
                    # Comfort mode isn't away and we aren't in a home hold
                    self.log('Setting an away hold.')
                    self.call_service(
                        service = 'climate/set_preset_mode',
                        entity_id = ecobee_entity,
                        preset_mode = 'away'
                    )
                elif preset_mode and climate_mode in away_modes:
                    # Away during a hold and comfort setting is an away setting
                    self.log('Resuming action (away).')
                    self.call_service(
                        service = 'climate/ecobee_resume_program',
                        entity_id = ecobee_entity,
                        resume_all = True
                    )


    # Update global variable and evaluate hold actions on presence change
    def presence_cb(self, entity, attribute, old, new, kwargs):
        self.global_vars['ecobee']['home_status'] = new
        if self.get_state(self.args['constrain_boolean']) == 'on':
            self.ecobee_actions()


    # Evaluate hold action when boolean is turned on, set a resume all when it's switched off
    def constrain_boolean_cb(self, entity, attribute, old, new, kwargs):
        if new == 'on':
            self.ecobee_actions()
        elif new == 'off':
            self.log('Resuming action (disabled).')
            self.call_service(
                service = 'climate/ecobee_resume_program',
                entity_id = self.args['ecobee_entity'],
                resume_all = True
            )


    # When ecobee state changes, re-evaluate hold actions
    def ecobee_state_cb(self, entity, attribute, old, new, kwargs):
        self.ecobee_actions()