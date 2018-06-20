import appdaemon.plugins.hass.hassapi as hass

class Lights(hass.Hass):

    def initialize(self):
        self.app_config['lights']['Test'] = "test"
        
        self.log(self.app_config['lights']['Test'])