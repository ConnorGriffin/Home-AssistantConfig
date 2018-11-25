import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime

class Utils(hass.Hass):

    def initialize(self):
        return


    def state_duration(self, entity):
        state = self.get_state(entity, attribute='all')
        now = datetime.utcnow()
        last_changed = self.convert_utc(state['last_changed']).replace(tzinfo=None)

        return (now - last_changed).total_seconds()
