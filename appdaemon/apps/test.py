import appdaemon.plugins.hass.hassapi as hass

class OneshotTest(hass.Hass):

    def initialize(self):

        self.listen_state(
            self.state_log,
            entity = 'input_boolean.test_switch',
            new = 'on',
            oneshot = True
        )

        self.listen_state(
            self.state_log,
            entity = 'input_boolean.test_switch2',
            new = 'on',
            oneshot = True
        )

        self.log("Test loaded")

    def state_log(self, entity, attribute, old, new, kwargs):
        self.log('{}/{}: {} -> {}'.format(entity, attribute, old, new))

class NotifyTest(hass.Hass):

    def initialize(self):

        self.notify(
            message = 'Notification Test',
            name = 'gcm_html5',
            target = 'Connor Phone'
        )
