import appdaemon.plugins.hass.hassapi as hass

class Presence(hass.Hass):

    def initialize(self):
        for room in self.args.get('rooms',[]):
            self.listen_state(
                self.occupancy_cb,
                entity = room['entity'], 
                name = room['name'],
                immediate = True
            )
    

    def occupancy_cb(self, entity, attribute, old, new, kwargs):
        name = kwargs.get('name','Unnamed room')
        self.log('{}: {} -> {}'.format(name, old, new))