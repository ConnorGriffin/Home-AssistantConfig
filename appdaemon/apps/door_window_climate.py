import appdaemon.plugins.hass.hassapi as hass
import datetime

class DoorWindowClimate(hass.Hass):

    def initialize(self):
        # TODO: Send zone status back to AppDaemon as a state/event input
        # TODO: Create actions based on climate rules
        # TODO: Handle temperature deltas, climate control, rest of the script basically

        self.data = {}

        for zone in self.args.get('zones', []):
            windows = zone.get('windows', [])
            doors = zone.get('doors', [])
            temp_source = zone.get('temp_source', self.args.get('temp_source')).split(':')
            temp_entity = temp_source[0]
            temp_attribute = temp_source[1]

            self.log(
                self.get_state(temp_entity, attribute=temp_attribute)
            )


            # Setup a persistent data store for each zone
            self.data[zone['name']] = {
                'state': None,
                'open_sensors': [],
                'closed_sensors': [],
                'total_sensors': len(windows) + len(doors)
            }

            # Pull in the settings for each zone, otherwise use the default settings
            door_open_seconds = zone.get('door_open_seconds', self.args['door_open_seconds'])
            door_closed_seconds = zone.get('door_closed_seconds', self.args['door_closed_seconds'])
            window_open_seconds = zone.get('window_open_seconds', self.args['window_open_seconds'])
            window_closed_seconds = zone.get('window_closed_seconds', self.args['window_closed_seconds'])

            # Setup listeners for each window
            for window in windows:
                self.listen_state(
                    cb = self.sensor_cb,
                    entity = window,
                    new = 'Closed',
                    duration = window_closed_seconds,
                    immediate = True,
                    zone = zone['name'],
                    mode = zone['mode']
                )

            # Setup listeners for each door
            for door in doors:
                self.listen_state(
                    cb = self.sensor_cb,
                    entity = door,
                    new = 'Closed',
                    duration = door_closed_seconds,
                    immediate = True,
                    zone = zone['name'],
                    mode = zone['mode']
                )


    def sensor_cb(self, entity, attribute, old, new, kwargs):
        zone = kwargs.get('zone')
        mode = kwargs.get('mode')

        # Add or remove the sensor from the open_sensors and closed_sensors lists
        if new == 'Closed':
            self.data[zone]['closed_sensors'].append(entity)
            if entity in self.data[zone]['open_sensors']:
                self.data[zone]['open_sensors'].remove(entity)
        elif new == 'Open':
            self.data[zone]['open_sensors'].append(entity)
            if entity in self.data[zone]['closed_sensors']:
                self.data[zone]['closed_sensors'].remove(entity)

        # Determine if the zone should be considered opened or closed based on mode and sensor counts
        open_count = len(self.data[zone]['open_sensors'])
        closed_count = len(self.data[zone]['closed_sensors'])

        # Set zone state once all sensors are accounted for
        if (open_count + closed_count) == self.data[zone]['total_sensors']:
            if mode == 'any':
                if open_count >= 1:
                    self.log('{} is open'.format(zone))
                    self.data[zone]['state'] = 'open'
                else:
                    self.log('{} is closed'.format(zone))
                    self.data[zone]['state'] = 'closed'
            elif mode == 'all':
                if closed_count >= 1:
                    self.log('{} is closed'.format(zone))
                    self.data[zone]['state'] = 'closed'
                else:
                    self.log('{} is open'.format(zone))
                    self.data[zone]['state'] = 'open'
