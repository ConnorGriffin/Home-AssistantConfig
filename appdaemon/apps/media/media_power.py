# Media Power - Controls media center power
#
# Setup:
#  - Projector is hooked up to a smart outlet, receiver is in a normal outlet.
#  - Projector 'Direct Power' is enabled and 'HDMI Link' is set to 'Mutual'.
#
# Result:
#  - As soon as I turn on the smart outlet the projector and receiver both turn on
#  - When the projector auto-powers off or is turned off with the remote, the receiver turns off
#  - When the receiver is turned off the projector also turns off
#
# This app picks up the missing pieces, automatically turning the smart switch back off if the projector turns off,
# and also turns on the projector if the roku is activated by the roku app (we lost our remote.)
#
# TODO: Eventually I would like to also look into custom alexa/google assistant intents, powering off lights, etc.
# TODO: Would also like to purchase an IR blaster to avoid needing the smart switch at all.

import appdaemon.plugins.hass.hassapi as hass
from datetime import timedelta

class MediaPower(hass.Hass):

    def initialize(self):

        power_switch = self.args['plug']['switch']
        plug_status = self.args['plug']['status']
        self.auto_on = None

        # Listen for plug to be inactive for 'off_duration' seconds
        self.listen_state(
            cb = self.power_cb,
            entity = plug_status,
            new = 'off',
            duration = self.args['off_duration'],
            immediate = True,
            power_switch = power_switch,
            constrain_input_boolean = power_switch
        )

        # Listen for the roku channel to change, but only if the power switch is off
        self.listen_state(
            cb = self.roku_cb,
            entity = self.args['roku'],
            power_switch = power_switch,
            constrain_input_boolean = '{},off'.format(power_switch),
            plug_status = plug_status
        )


    def power_cb(self, entity, attribute, old, new, kwargs):
        power_switch = kwargs['power_switch']

        # Don't turn off the plug if it recently turned on (takes a few seconds for the sensor to update)
        if self.auto_on:
            if (self.datetime() - self.auto_on).total_seconds() <= 60:
                pass
        else:
            # Turn off the plug once it's been inactive for a set amount of time
            self.log('Plug inactive for {} seconds, switching off.'.format(self.args['off_duration']))
            self.turn_off(power_switch)


    def roku_cb(self, entity, attribute, old, new, kwargs):
        # Turn the smart switch on if roku changes from idle
        power_switch = kwargs['power_switch']

        if old in ['home', 'idle'] and new not in ['home', 'idle']:
            self.log('Roku channel changed from {}, turning on power.'.format(old))
            self.turn_on(power_switch)
            self.auto_on = self.datetime()