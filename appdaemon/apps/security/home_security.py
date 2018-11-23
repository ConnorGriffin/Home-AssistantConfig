# Home Security Alarm - Monitors door/window sensors for changes when nobody is home.
# Issues a push notification to the specified notification targets, allowing the users to rearm or disarm the alarm.
#
# Fires if nobody is home and either of the following occurs:
#   * A door or window changes state and holds the change for 'open_duration' seconds
#   * A door or window changes state for any amount of time and nobody registers as home within 'return_delay' seconds
#
# This allows us to capture a window or door being left open for an extended period by an intruder, but also alarms when
#   a door or window is open for a short period of time, while avoiding false positives when an actual occupant returns home
#   but hasn't been picked up by HomeAssistant yet.

import appdaemon.plugins.hass.hassapi as hass

class HomeSecurity(hass.Hass):

    def initialize(self):
        # Store whether the alarm is armed and fired or not
        self.alarm_armed = False
        self.alarm_fired = False

        # Create the sensors in HA for reporting in the GUI
        self.set_state(
            entity_id = self.args['armed_sensor'],
            state = 'False',
            attributes = {
                'friendly_name': "Home Security Armed",
                'icon': 'mdi:security-off'
            }
        )
        self.set_state(
            entity_id = self.args['fired_sensor'],
            state = 'Clear',
            attributes = {
                'friendly_name': "Home Security Alarm",
                'icon': 'mdi:security-home'
            }
        )

        # Setup an array of handles to cancel later (until oneshot fix is live in 3.0.3)
        self.sensor_handles = []
        self.timer_handles = []

        # Store sensor counts
        self.sensors = {
            'open_sensors': 0,
            'closed_sensors': 0,
            'total_sensors': len(self.args['door_window_sensors'])
        }

        # Listen for nobody to be home for the set duration
        self.listen_state(
            cb = self.presence_cb,
            entity = self.args['presence_entity'],
            new = 'off',
            duration = self.args['arm_delay'],
            immediate = True
        )

        # Listen for someone to return home
        self.listen_state(
            cb = self.presence_cb,
            entity = self.args['presence_entity'],
            old = 'off',
            new = 'on'
        )

        # Listen for the notification to be clicked
        self.listen_event(
            cb = self.notification_clicked_cb,
            event = 'html5_notification.clicked',
            tag = 'home-security-alarm'
        )


    # Arm or disarm the alarm depending on the presence and alarm states
    def presence_cb(self, entity, attribute, old, new, kwargs):
        if new == 'off' and not self.alarm_armed:
            # Arm the alarm when nobody is home
            self.arm_alarm()
        elif new == 'on' and self.alarm_armed:
            # Disarm the alarm when someone is home
            self.disarm_alarm()


    # Arms or re-arms the alarm
    def arm_alarm(self):
        self.log('Alarm armed.')
        self.alarm_armed = True
        self.alarm_fired = False

        # Update the sensors in HA
        self.set_state(
            entity_id = self.args['armed_sensor'],
            state = 'True',
            attributes = {
                'icon': 'mdi:security'
            }
        )
        self.set_state(
            entity_id = self.args['fired_sensor'],
            state = 'Clear',
            attributes = {
                'icon': 'mdi:security-home'
            }
        )

        # Cancel any existing sensor listeners before re-enabling
        for handle in self.sensor_handles:
            self.cancel_listen_state(handle)
            self.sensor_handles.remove(handle)

        # Cancel any existing timers before re-enabling
        for handle in self.timer_handles:
            self.cancel_timer(handle)
            self.timer_handles.remove(handle)

        # Setup two listeners for each sensor. One fires after the sensor state is changed for 30 seconds. The other...
        # fires immediately, but the callback checks if someone returns home in 'return_delay' seconds before firing...
        # the alarm. This avoids false positives with a legitimate occupant returning home and tripping the alarm.
        for sensor in self.args['door_window_sensors']:
            # Listen for the opposite of the current state
            current_state = self.get_state(sensor)
            if current_state == 'on':
                new_state = 'off'
            elif current_state == 'off':
                new_state = 'on'

            # Setup the listeners and add the handler to the handle array, oneshots fixed in 3.0.3, not working right now.
            handle = self.listen_state(
                cb = self.sensor_cb,
                entity = sensor,
                old = current_state,
                new = new_state,
                duration = self.args['open_duration']
            )
            self.sensor_handles.append(handle)

            handle = self.listen_state(
                cb = self.sensor_cb,
                entity = sensor,
                old = current_state,
                new = new_state,
                check_returned_home = True
            )
            self.sensor_handles.append(handle)

    # Disarms the alarm
    def disarm_alarm(self):
        self.log('Alarm disarmed.')
        self.alarm_armed = False
        self.alarm_fired = False

        # Update the sensors in HA
        self.set_state(
            entity_id = self.args['armed_sensor'],
            state = 'False',
            attributes = {
                'icon': 'mdi:security-off'
            }
        )
        self.set_state(
            entity_id = self.args['fired_sensor'],
            state = 'Clear',
            attributes = {
                'icon': 'mdi:security-home'
            }
        )

        # Cancel any state listeners
        for handle in self.sensor_handles:
            self.cancel_listen_state(handle)
            self.sensor_handles.remove(handle)

        # Cancel any existing timers
        for handle in self.timer_handles:
            self.cancel_timer(handle)
            self.timer_handles.remove(handle)


    # Take action when a sensor changes state while the alarm is armed
    def sensor_cb(self, entity, attribute, old, new, kwargs):
        check_returned_home = kwargs.get('check_returned_home', False)

        if check_returned_home:
            handle = self.run_in(
                self.check_returned_home,
                seconds = self.args['return_delay'],
                entity_id = entity,
                old = old,
                new = new
            )
            self.timer_handles.append(handle)
        else:
            self.fire_alarm(
                entity = entity,
                old = old,
                new = new
            )


    # Check if someone has returned home after a sensor state is changed. If not, fire the alarm if it hasn't already fired.
    def check_returned_home(self, kwargs):
        if self.alarm_armed and not self.alarm_fired:
            state = self.get_state(self.args['presence_entity'])
            if state == 'off':
                self.fire_alarm(
                    entity = kwargs['entity_id'],
                    old = kwargs['old'],
                    new = kwargs['new']
                )


    # Fire the alarm notification and any other actions
    def fire_alarm(self, entity, old, new):
        self.log('Alarm triggered.')
        self.alarm_fired = True

        # Update the sensor in HA
        self.set_state(
            entity_id = self.args['fired_sensor'],
            state = 'Alarming',
            attributes = {
                'icon': 'mdi:alarm-light'
            }
        )

        # Send a notification
        self.notify(
            title = 'Home Security Alarm',
            message = 'Alart: {} changed from {} to {}'.format(self.friendly_name(entity), old, new),
            name = 'gcm_html5',
            target = self.args['notification_targets'],
            data = {
                "tag": "home-security-alarm",
                "actions": [{
                    "action": "rearm",
                    "title": "Acknowledge (Rearm)"
                }, {
                    "action": "disarm",
                    "title": "Ignore (Disarm)"
                }]
            }
        )


    # Take action based on notification actions
    def notification_clicked_cb(self, event_name, data, kwargs):
        # Arm or disarm the alarm based on the action
        if data['action'] == 'disarm':
            self.log('Alarm disarmed by {}'.format(data['target']))
            self.disarm_alarm()
        elif data['action'] == 'rearm':
            self.log('Alarm rearmed by {}'.format(data['target']))
            self.arm_alarm()
