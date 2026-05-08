from sql_manager import SQLManager

class PolarMapService:
    def __init__(self):
        self.tws = None
        self.twa = None
        self.boat_speed = None
        self.initialized = False
        self.threshold = 26.5
        self.SQLManager = SQLManager()
        self.all_fields_ready_to_write = {
            "twa": False, 
            "tws": False, 
            "boat_speed": False
        }

    def initialize(self, depth):
        if depth > self.threshold:
            self.initialized = True

    def add_field(self):
        if self.initialized and self.is_data_ready():
            self.SQLManager.add_data(self.tws, self.twa, self.boat_speed)
            for key in self.all_fields_ready_to_write.keys(): 
                self.all_fields_ready_to_write[key] = False
        
    def is_data_ready(self): 
        return all(self.all_fields_ready_to_write.values())
        
    def set_module(self, module_name: str, value: float):
        if self.all_fields_ready_to_write.get(module_name, -1) == -1: 
            return  
        
        self.all_fields_ready_to_write[module_name] = True
        setattr(self, module_name, value)