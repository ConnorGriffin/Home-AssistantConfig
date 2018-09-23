import appdaemon.plugins.hass.hassapi as hass
import json
import requests

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

    def get_home_occupancy(self):
        # TODO: EVERYTHING

        # define endpoint and credentials
        api_key = self.config['opnsense']['api_key']
        api_secret = self.config['opnsense']['api_secret']
        url = 'https://10.31.36.1/api/core/firmware/status'

        # request data
        r = requests.get(url,
                        verify=False,
                        auth=(api_key, api_secret))

        if r.status_code == 200:
            response = json.loads(r.text)

            if response['status'] == 'ok' and response['status_upgrade_action'] == 'all':
                self.log ('OPNsense can be upgraded')
                self.log ('download size : %s' % response['download_size'])
                self.log ('number of packages : %s' % response['updates'])
                if response['upgrade_needs_reboot'] == '1':
                    self.log ('REBOOT REQUIRED')
            elif response['status'] == 'ok' and response['status_upgrade_action'] == 'pkg':
                self.log ('OPNsense can be upgraded, but needs a pkg upgrade first')
            elif 'status_msg' in response:
                self.log (response['status_msg'])
        else:
            self.log ('Connection / Authentication issue, response received:')
            #self.log r.text