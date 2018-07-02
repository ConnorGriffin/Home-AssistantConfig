import appdaemon.plugins.hass.hassapi as hass
import importlib
import subprocess

class InstallDeps(hass.Hass):

    def initialize(self):
        for package in self.args.get('packages',[]):
            try:
                importlib.import_module(package)
                self.log('{} already installed'.format(package))
            except ImportError:
                self.install(package)
    

    def install(self, package):
        self.log('Installing {}'.format(package))
        subprocess.call(['pip3', 'install', package])
