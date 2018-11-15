import appdaemon.plugins.hass.hassapi as hass
import re

class TemplateSensor(hass.Hass):

    def initialize(self):

        # If an attribute is provided use that, otherwise just get the state
        attribute = self.args.get('attribute', 'state')

        # Iterate over each entity to create listeners and sensors
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
                attribute = attribute,
                sensor = sensor,
                friendly_name = friendly_name
            )

            # Listen for
            self.listen_state(
                cb = self.sensor_cb,
                entity = entity_id,
                attribute = attribute,
                sensor = sensor,
                friendly_name = friendly_name
            )


    def sensor_cb(self, entity, attribute, old, new, kwargs):
        # Call the update_sensor function when a sensor state changes
        self.update_sensor(
            entity = entity,
            attribute = attribute,
            sensor = kwargs['sensor'],
            new = new,
            friendly_name = kwargs.get('friendly_name', None)
        )


    def update_sensor(self, entity, attribute, sensor, **kwargs):
        # Get the new value if provided, otherwise get state
        new = kwargs.get('new', self.get_state(entity, attribute=attribute))

        # Get the friendly name if provided, otherwise use a title-cased version of the entity ID
        friendly_name = kwargs.get('friendly_name', None)
        if not friendly_name:
            friendly_name = sensor.split('.')[1].replace('_', ' ').title()

        # Set new_state based on whether this is a binary_sensor or not
        if self.args['type'] == 'binary_sensor':
            # Get values and expressions (only one or the other should be provided)
            on_value = self.args.get('on_value', None)
            off_value = self.args.get('off_value', None)
            on_expression = self.args.get('on_expression', None)
            off_expression = self.args.get('off_expression', None)

            # Use the values or expressions depending on which is provided (prefer values over expressions)
            if bool(on_value and off_value):
                # Compare the new value to the expected on/off values
                if new == on_value:
                    new_state = 'on'
                elif new == off_value:
                    new_state = 'off'
                else:
                    new_state = 'unknown'
            elif bool(on_expression and off_expression):
                # Compare the new value to the expected on/off expressions
                on_exp_string = '{} {}'.format(new, on_expression)
                off_exp_string = '{} {}'.format(new, off_expression)

                if eval(on_exp_string):
                    new_state = 'on'
                elif eval(off_exp_string):
                    new_state = 'off'
                else:
                    new_state = 'unknown'
            else:
                new_state = 'unknown'
        else:
            new_state = new

        # Dynamically build the attributes dict
        attributes = {
            'friendly_name': friendly_name
        }
        if self.args['device_class']:
            attributes.update({'device_class': self.args['device_class']})
        if self.args['icon']:
            attributes.update({'icon': self.args['icon']})

        # Update the sensor
        self.set_state(
            entity_id = sensor,
            state = new_state,
            attributes = attributes
        )
