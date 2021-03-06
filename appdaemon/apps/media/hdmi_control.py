""" HDMI Control - HDMI/CEC Related Automations

Projector Switch:
- Turn receiver on if projector switch is turned on (ties the two together)

Roku Power Control:
- Turn projector on if Roku channel changes from home/idle

Receiver Volume:
- Update the volume slider when the volume sensor updates (slider is decoupled from sensor)
"""

import appdaemon.plugins.hass.hassapi as hass
from helpers import Helpers as helpers


class ProjectorSwitch(hass.Hass):

    def initialize(self):

        # Turn receiver on if projector switch is turned on and receiver is off
        self.listen_state(
            callback=self.projector_switch_cb,
            entity=self.args['projector'],
            old='off',
            new='on',
            constrain_input_boolean='{},off'.format(self.args['receiver']),
        )

    def projector_switch_cb(self, entity, attribute, old, new, kwargs):
        if new == 'on':
            self.turn_on(self.args['receiver'])


class RokuPowerControl(hass.Hass):

    def initialize(self):
        # Turn projector on if Roku changes from home/idle and the projector is off
        self.listen_state(
            callback=self.roku_cb,
            entity=self.args['roku'],
            constrain_input_boolean='{},off'.format(self.args['projector'])
        )

    def roku_cb(self, entity, attribute, old, new, kwargs):
        # Don't do anything if old is None (having issues after restarts)
        if old in ['home', 'idle'] and new not in ['home', 'idle']:
            self.log(
                'Roku channel changed from {} to {}, turning on projector.'.format(old, new))
            self.turn_on(self.args['projector'])


class ReceiverVolume(hass.Hass):

    def initialize(self):
        # Update the volume slider when the volume sensor updates
        self.listen_state(
            callback=self.volume_state_cb,
            entity=self.args['volume_sensor']
        )

    def volume_state_cb(self, entity, attribute, old, new, kwargs):
        # In 5 seconds check if the volume has stayed the same for 5 seconds
        self.run_in(
            self.volume_scheduler_cb,
            delay=5,
            value=new
        )

    def volume_scheduler_cb(self, kwargs):
        value = kwargs['value']
        volume_sensor = self.args['volume_sensor']
        state = self.get_state(volume_sensor)

        if state == value:
            duration = helpers.state_duration(self, volume_sensor)
            if abs(duration - 5) < 1:
                self.log('Setting volume slider to: {}%'.format(value))
                self.call_service(
                    service='input_number/set_value',
                    entity_id=self.args['volume_slider'],
                    value=value
                )
