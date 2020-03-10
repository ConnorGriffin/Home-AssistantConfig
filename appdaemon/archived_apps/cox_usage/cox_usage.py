# cox_usage.py
# Script designed to get Cox Communications internet
# usage data into a JSON format for Home Assistant.
#
# Version 1.0
# Original Author : Rick Rocklin
# Original Date   : 10/02/2017
#
# 10/17/2017: Output to file
# 11/02/2017: Updated to use mechanicalsoup
# 11/26/2018: Adapted by Connor Griffin for AppDaemon

import appdaemon.plugins.hass.hassapi as hass
import mechanicalsoup
import re
import json
from calendar import monthrange

class CoxUsage(hass.Hass):

    def initialize(self):
        # Update internet usage sensors every hour. May need to cut back to daily, not sure how often cox updates.
        self.run_every(
            callback = self.cox_usage_cb,
            start = self.datetime(),
            interval = 3600
        )


    def cox_usage_cb(self, kwargs):
        # URL that we authenticate against
        login_url = "https://www.cox.com/resaccount/sign-in.cox"

        # URL that we grab all the data from
        stats_url = "https://www.cox.com/internet/mydatausage.cox"

        # Your cox user account (e.g. username@cox.net) and password
        cox_user = self.config['cox']['username']
        cox_pass = self.config['cox']['password']

        # Setup browser
        browser = mechanicalsoup.StatefulBrowser(
            soup_config={'features': 'lxml'},
            user_agent='Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.13) Gecko/20101206 Ubuntu/10.10 (maverick) Firefox/3.6.13',
        )

        # Disable SSL verification workaround for issue #2
        browser.session.verify = False

        # Open the login URL
        login_page = browser.get(login_url)

        # Similar to assert login_page.ok but with full status code in case of failure.
        login_page.raise_for_status()

        # Find the form named sign-in
        login_form = mechanicalsoup.Form(
            login_page.soup.select_one('form[name="sign-in"]')
        )

        # Specify username and password
        login_form.input({'username': cox_user, 'password': cox_pass})

        # Submit the form
        browser.submit(login_form, login_page.url)

        # Read the stats URL
        stats_page = browser.get(stats_url)

        # Grab the script with the stats in it
        stats = stats_page.soup.findAll(
            'script', string=re.compile('utag_data'))[0].string

        # Split and RSplit on the first { and on the last } which is where the data object is located
        jsonValue = '{%s}' % (stats.split('{', 1)[1].rsplit('}', 1)[0],)

        # Load into json
        data = json.loads(jsonValue)

        # Post the sensor states to Home Assistant
        usage = int(data.get('dumUsage'))
        limit = int(data.get('dumLimit'))
        days_left = int(data.get('dumDaysLeft'))

        if usage:
            usage_pct = usage / limit * 100
        else:
            usage_pct = 0

        # Raw data
        self.set_state(
            entity_id = 'sensor.cox_usage',
            state = usage,
            attributes = {
                'friendly_name': 'Cox Usage',
                'unit_of_measurement': 'GB',
                'icon': 'mdi:chart-line-variant'
            }
        )
        self.set_state(
            entity_id = 'sensor.cox_limit',
            state = limit,
            attributes = {
                'friendly_name': 'Cox Limit',
                'unit_of_measurement': 'GB',
                'icon': 'mdi:gauge-full'
            }
        )
        self.set_state(
            entity_id = 'sensor.cox_days_left',
            state = days_left,
            attributes = {
                'friendly_name': 'Cox Days Left',
                'unit_of_measurement': 'Days',
                'icon': 'mdi:calendar-clock'
            }
        )
        self.set_state(
            entity_id = 'sensor.cox_usage_percent',
            state = round(usage_pct, 2),
            attributes = {
                'friendly_name': 'Cox Usage Percent',
                'unit_of_measurement': '%',
                'icon': 'mdi:percent'
            }
        )

        # Calculated/formatted data
        self.set_state(
            entity_id = 'sensor.cox_utilization',
            state = '{} / {} GB ({}%)'.format(usage, limit, round(usage_pct)),
            attributes = {
                'friendly_name': 'Cox Utilization',
                'unit_of_measurement': None,
                'icon': 'mdi:percent'
            }
        )

        now = self.datetime()
        days_in_month = monthrange(now.year, now.month)[1]
        days_passed = max(1, days_in_month - days_left)
        average_daily_usage = usage / days_passed
        remaining_data = max(0, limit - usage)

        if days_left == 0:
            remaining_daily_usage = remaining_data
        else:
            if remaining_data != 0:
                remaining_daily_usage = remaining_data / days_left
            else:
                remaining_daily_usage = 0

        self.set_state(
            entity_id = 'sensor.cox_average_daily_usage',
            state = round(average_daily_usage, 2),
            attributes = {
                'friendly_name': 'Cox Average Daily Usage',
                'unit_of_measurement': 'GB',
                'icon': 'mdi:chart-line'
            }
        )

        self.set_state(
            entity_id = 'sensor.cox_remaining_daily_usage',
            state = round(remaining_daily_usage, 2),
            attributes = {
                'friendly_name': 'Cox Remaining Daily Usage',
                'unit_of_measurement': 'GB',
                'icon': 'mdi:chart-line-stacked'
            }
        )
