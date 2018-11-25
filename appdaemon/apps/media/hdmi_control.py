import appdaemon.plugins.hass.hassapi as hass
from helpers import Utils

class ProjectorSwitch(hass.Hass):

    def initialize(self):

        # Turn receiver on if projector switch is turned on and receiver is off
        self.listen_state(
            cb = self.projector_switch_cb,
            entity = self.args['projector'],
            old = 'off',
            new = 'on',
            constrain_input_boolean = '{},off'.format(self.args['receiver']),
        )


    def projector_switch_cb(self, entity, attribute, old, new, kwargs):
        if new == 'on':
            self.turn_on(self.args['receiver'])


class RokuPowerControl(hass.Hass):

    def initialize(self):

        # Turn projector off if Roku is on home screen for 5 minutes and the projector is on
        self.listen_state(
            cb = self.roku_cb,
            entity = self.args['roku'],
            duration = self.args['idle_duration'],
            constrain_input_boolean = self.args['projector']
        )

        # Turn projector on if Roku changes from home/idle and the projector is off
        self.listen_state(
            cb = self.roku_cb,
            entity = self.args['roku'],
            constrain_input_boolean = '{},off'.format(self.args['projector'])
        )

    def roku_cb(self, entity, attribute, old, new, kwargs):
        # Don't do anything if old is None (having issues after restarts)
        if old:
            # Turn off if idle
            if new in ['home', 'idle']:
                self.log('Roku changed from {} to {}, turning off projector.'.format(old, new))
                self.turn_off(self.args['projector'])

            # Turn on if channel changes
            elif old in ['home', 'idle'] and new not in ['home', 'idle']:
                self.log('Roku channel changed from {} to {}, turning on projector.'.format(old, new))
                self.turn_on(self.args['projector'])


class ReceiverVolume(Utils):

    def initialize(self):

        # Update the volume slider when the volume sensor updates
        self.listen_state(
            cb = self.volume_state_cb,
            entity = self.args['volume_sensor']
        )


    def volume_state_cb(self, entity, attribute, old, new, kwargs):
        # In 5 seconds check if the volume has stayed the same for 5 seconds
        self.run_in(
            self.volume_scheduler_cb,
            seconds = 5,
            value = new
        )


    def volume_scheduler_cb(self, kwargs):
        value = kwargs['value']
        volume_sensor = self.args['volume_sensor']
        state = self.get_state(volume_sensor)

        if state == value:
            duration = self.state_duration(volume_sensor)
            if abs(duration - 5) < 1:
                self.log('Setting volume slider to: {}%'.format(value))
                self.call_service(
                    service = 'input_number/set_value',
                    entity_id = self.args['volume_slider'],
                    value = value
                )
