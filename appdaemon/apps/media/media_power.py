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
# TODO: Eventually I would like to also look into custom alexa intents, powering off lights, etc.
# TODO: Would also like to purchase an IR blaster to avoid needing the smart switch at all.

import appdaemon.plugins.hass.hassapi as hass

class MediaPower(hass.Hass):

    def initialize(self):

        # Listen for plug to be inactive for 'off_duration' seconds
        self.listen_state(
            cb = self.power_cb,
            entity = self.args['plug']['status'],
            new = 'off',
            duration = self.args['off_duration'],
            immediate = True,
            switch = self.args['plug']['switch']
        )


    def power_cb(self, entity, attribute, old, new, kwargs):
        # Turn off the plug once it's been inactive for a set amonut of time
        switch = kwargs['switch']
        self.log('Plug inactive for {} seconds, switching off.'.format(self.args['off_duration']))
        self.turn_off(switch)


    def roku_cb(self, entity, attribute, old, new, kwargs):
        # Turn the smart switch on if roku changes from idle
        switch = kwargs['switch']
        self.log('Roku channel changed, turning on smart switch.')