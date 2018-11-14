import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime, timedelta
from lxml import html
import requests
import csv

class SrpUsage(hass.Hass):

    def initialize(self):
        self.log("")
        # Get these from global config using secrets
        #username = 
        #password = 
        #account = 


    def get_usage(self, kwargs):
        # Set the SRP myaccount url and get yesterday's date in a format that the report expects
        srp_url = 'https://myaccount.srpnet.com'
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%m/%d/%Y')

        # Create a session so our login persists
        session = requests.session()

        # Get the page and parse into an object
        response = session.get(srp_url)
        tree = html.fromstring(response.text)

        # Get the login form
        for form in tree.forms:
            if form.action == '/sso/Login/LoginUser':
                login_form = form
                break

        # POST a login request
        login_form.fields['UserName'] = username 
        login_form.fields['Password'] = password
        response = session.post('{}{}'.format(srp_url, login_form.action), data=login_form.form_values())

        # Set the URL query options
        export_params = [
            'billAccount={}'.format(account),
            'viewDataType=DisplayCostkWh',
            'reportOption=Hourly',
            'startDate={}'.format(yesterday),
            'endDate={}'.format(yesterday),
            'displayCost=false'
        ]
        export_params = '&'.join(export_params)
        report_url = '{}{}{}'.format(srp_url, '/MyAccount/Usage/ExportToExcel?', export_params)

        # Generate and decode the CSV report
        response = session.get(report_url)
        data = response.content.decode('utf-8-sig')

        # Return the csv data as an array of dicts
        reader = csv.DictReader(data.splitlines(), delimiter=',')
        data_table = []
        for row in list(reader):
            data_table.append(row)
        
        return data_table