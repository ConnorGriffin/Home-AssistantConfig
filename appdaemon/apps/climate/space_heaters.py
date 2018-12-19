import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta

class SpaceHeaters(hass.Hass):

    def initialize(self):

        now_dt = datetime.now()
        now_time = self.time()
        today_start = datetime(now_dt.year, now_dt.month, now_dt.day)
        tomorrow_start = today_start + timedelta(1)

        for heater_config in self.args['heaters']:
            for schedule_entry in heater_config['schedule']:
                start_time = self.parse_time(schedule_entry['start'])
                end_time = self.parse_time(schedule_entry['end'])

                # Create datetime object from the start time, set to tomorrow if time has already passed
                if start_time <= now_time:
                    start_dt = datetime.combine(tomorrow_start, start_time)
                else:
                    start_dt = datetime.combine(today_start, start_time)

                if end_time <= now_time:
                    end_dt = datetime.combine(tomorrow_start, end_time)
                else:
                    end_dt = datetime.combine(today_start, end_time)


                self.log(start_dt)
                self.log(end_dt)

                # Setup a daily schedule call for the begin and end operations
                self.run_every(
                    callback = self.set_operation_mode,
                    start = start_dt,
                    interval = 86400,
                    room = heater_config['room'],
                    climate = heater_config['climate'],
                    operation_mode = schedule_entry['start_operation']
                )

                self.run_every(
                    callback = self.set_operation_mode,
                    start = end_dt,
                    interval = 86400,
                    room = heater_config['room'],
                    climate = heater_config['climate'],
                    operation_mode = schedule_entry['end_operation']
                )


    def set_operation_mode(self, kwargs):
        room = kwargs['room']
        climate = kwargs['climate']
        operation_mode = kwargs['operation_mode']

        self.log('Setting {} space heater ({}) to {}.'.format(room, climate, operation_mode))

        self.call_service(
            service = 'climate/set_operation_mode',
            entity_id = climate,
            operation_mode = operation_mode
        )
