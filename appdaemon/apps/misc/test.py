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
            target = 'Connor Desktop',
            data = {
                "actions": [
                {
                    "action": "open",
                    "icon": "/static/icons/favicon-192x192.png",
                    "title": "Open Home Assistant"
                },
                {
                    "action": "open_door",
                    "title": "Open door"
                }
                ]
            }
        )

        self.listen_event(
            cb = self.event_cb,
            event = 'html5_notification.received'
        )

        self.listen_event(
            cb = self.event_cb,
            event = 'html5_notification.clicked',
            target = 'Connor Phone',
            action = 'open'
        )

        self.listen_event(
            cb = self.event_cb,
            event = 'html5_notification.closed'
        )



    def event_cb(self, event_name, data, kwargs):
        self.log(event_name)
        self.log(data)

