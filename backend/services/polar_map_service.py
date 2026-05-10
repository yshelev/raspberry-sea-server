from sql_manager import SQLManager
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PolarMapService:
    def __init__(self):
        self.tws = None
        self.twa = None
        self.boat_speed = None
        self.initialized = False
        self.threshold = 5
        self.SQLManager = SQLManager()
        self.wind_bins_step = 2

    def initialize(self, depth):
        if depth > self.threshold:
            logger.info("initialized")
            self.initialized = True

    async def add_field(self):
        if self.initialized and self.twa:
            await self.SQLManager.add_data(self.tws, self.twa, self.boat_speed)

    def set_module(self, module_name: str, value: float):
        if module_name == "tws":
            value = round(value / self.wind_bins_step) * self.wind_bins_step
        setattr(self, module_name, value)
