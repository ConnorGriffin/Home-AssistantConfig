import appdaemon.plugins.hass.hassapi as hass
import re

class TemplateSensor(hass.Hass):

    def initialize(self):

        # Setup
        for entity in self.args.get('entities', []):
            # If entity is provide as a key/value pair, extract the entity_id
            if type(entity) is dict:
                entity_id = entity['entity']
                friendly_name = entity['name']
            else:
                entity_id = entity
                friendly_name = None

            # Determine what to call the new sensor based on the regex provided
            sensor = re.sub(
                pattern = r'{}'.format(self.args['sensor_name']['find']),
                repl = self.args['sensor_name']['replace'],
                string = entity_id
            )

            # Set the value immediately (on AppDaemon startup)
            self.update_sensor(
                entity = entity_id,
                sensor = sensor,
                friendly_name = friendly_name
            )

            # Listen for
            self.listen_state(
                cb = self.sensor_cb,
                entity = entity_id,
                sensor = sensor,
                friendly_name = friendly_name
            )


    def sensor_cb(self, entity, attribute, old, new, kwargs):
        # Call the update_sensor function when a sensor state changes
        self.update_sensor(
            entity = entity,
            sensor = kwargs['sensor'],
            new = new,
            friendly_name = kwargs.get('friendly_name', None)
        )


    def update_sensor(self, entity, sensor, **kwargs):
        # Get the new value if provided, otherwise get state
        new = kwargs.get('new', self.get_state(entity))

        # Get the friendly name if provided, otherwise use a title-cased version of the entity ID
        friendly_name = kwargs.get('friendly_name', None)
        if not friendly_name:
            friendly_name = sensor.split('.')[1].replace('_', ' ').title()

        # Compare the new value to the expected on/off values
        if new == self.args['on_value']:
            new_state = 'on'
        elif new == self.args['off_value']:
            new_state = 'off'
        else:
            new_state = 'unknown'

        # Update the sensor
        self.set_state(
            entity_id = sensor,
            state = new_state,
            attributes = {
                'friendly_name': friendly_name,
                'device_class': self.args['device_class']
            }
        )
