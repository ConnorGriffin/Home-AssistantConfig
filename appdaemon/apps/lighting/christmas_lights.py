import appdaemon.plugins.hass.hassapi as hass

class ChristmasTreeLights(hass.Hass):

    def initialize(self):
        self.plug = 'switch.smart_plug_1'

        # Turn off lights at sunrise
        self.run_at_sunrise(self.plug_cb, action='off')

        # Turn on lights at sunset as long as projector is off
        self.run_at_sunset(
            self.plug_cb,
            constrain_input_boolean = 'switch.cec_projector,off',
            action = 'on'
        )

        # Turn on/off christmas tree lights when the projector is turned off/on
        self.listen_state(
            cb = self.projector_cb,
            entity = 'switch.cec_projector',
            new = 'on'
        )
        self.listen_state(
            cb = self.projector_cb,
            entity = 'switch.cec_projector',
            new = 'off',
            duration = 30
        )


    def plug_cb(self, kwargs):
        action = kwargs['action']
        if action == 'on':
            self.turn_on(self.plug)
        elif action == 'off':
            self.turn_off(self.plug)


    def projector_cb(self, entity, attribute, old, new, kwargs):
        # Turn off Christmas tree lights when projector turned on
        if new == 'on':
            self.turn_off(self.plug)

        # Turn on Christmas tree lights when projector turned off and sun is down
        if new == 'off' and self.sun_down():
            self.turn_on(self.plug)


