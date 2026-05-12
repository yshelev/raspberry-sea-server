from sql_manager import SQLManager
from services.graph_service import GraphService
from models.PolarSystemPoint import PolarSystemPoint
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
        self.wind_bins_step = 2
        self.data_count = 0
        self.data_threshold_for_diagram_create = 10
        
        self.SQLManager = SQLManager()
        self.graph_service = GraphService()        

    def initialize(self, depth):
        if depth > self.threshold:
            logger.info("initialized")
            self.initialized = True

    async def add_field(self):
        if self.initialized and self.twa:
            self.data_count += 1
            logger.info(f"DATACNT {self.data_count}")
            await self.SQLManager.add_data(
                self.tws,
                self.twa,
                self.boat_speed
            )

            if self.data_count > self.data_threshold_for_diagram_create: 
                self.data_count = 0
                
                save_path = await self._create_graph()
                return True, save_path 
                
        return False, None
                
    async def _create_graph(self): 
        rows = await self.SQLManager.fetch_data()
        
        polar_points = [
           PolarSystemPoint(
                twa=row['twa'],
                tws=row['tws'],
                boat_speed=row['boat_speed']
            ) 
            for row in rows
        ]
        
        save_path = self.graph_service.create_graph(polar_points)

        return save_path
        
    def set_module(self, module_name: str, value: float):
        if module_name == "tws":
            value = round(value / self.wind_bins_step) * self.wind_bins_step
        setattr(self, module_name, value)
