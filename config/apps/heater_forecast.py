import appdaemon.plugins.hass.hassapi as hass

class HeaterForecast(hass.Hass):
    def initialize(self):
        self.log("HeaterForecast loaded OK")
