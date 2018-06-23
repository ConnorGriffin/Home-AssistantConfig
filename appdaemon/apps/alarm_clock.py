import appdaemon.plugins.hass.hassapi as hass
import datetime

class AlarmClock(hass.Hass):

    def initialize(self):
        # Get the alarm clock groups in the alarm clock view, setup listeners for each
        alarm_groups = self.get_state('group.alarmclock_view', attribute='entity_id')
        for alarm in alarm_groups:
            alarm_name = alarm.split('.')[1]
            
            # Every miunte evaluate if alarm should trigger
            self.run_minutely(
                self.alarm_triggered_cb,
                datetime.datetime.now().time(),
                constrain_input_boolean='input_boolean.{}_enabled'.format(alarm_name),
                alarm_name=alarm_name
            )

    def alarm_triggered_cb(self, kwargs):
        alarm_name = kwargs.get('alarm_name')
        
        # Get the alarm properties
        enabled = self.get_state('input_boolean.{}_enabled'.format(alarm_name))
        time = self.get_state('input_datetime.{}_datetime'.format(alarm_name))
        alarm_seconds = (int(time.split(':')[0]) * 60 + int(time.split(':')[1])) * 60 + int(time.split(':')[2]) 
        
        # Get the total seconds since midnight, used to calculate alarm triggered time
        now = datetime.datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        now_seconds = (now - midnight).seconds

        #If the alarm time is before the current time, add 24 hours. This allows the script to run at 23:59 to trigger an alarm at 00:00
        if alarm_seconds < now_seconds:
            alarm_seconds += 86400 
            alarm_day = (now + datetime.timedelta(days=1)).strftime("%A").lower() 
        else:
            alarm_day = now.strftime("%A").lower()

        # Get the alarm day selector boolean for the current day (or whatever day the alarm is supposed to fire in)
        alarm_day_enabled = self.get_state('input_boolean.{}_{}'.format(alarm_name, alarm_day))

        # Determine if the alarm is set to go off within 60 seconds
        diff_seconds = alarm_seconds - now_seconds
        if diff_seconds > 0 and diff_seconds <= 60 and alarm_day_enabled == 'on': 
            # Fire the alarm 
            self.run_in(
                self.trigger_alarm,
                seconds=diff_seconds, 
                alarm_name=alarm_name,
            )

    def trigger_alarm(self, kwargs):
        alarm_name = kwargs.get('alarm_name')
        
        # Notify HomeAssistant that this alarm has triggered. Other AppDaemon apps can subscribe to this event to take action on the alarm 
        self.log('Fired {}.'.format(alarm_name))
        self.fire_event(
            "alarm_fired",
            alarm_name = alarm_name
        )