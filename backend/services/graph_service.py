import matplotlib.pyplot as plt
from collections import defaultdict
from models.PolarSystemPoint import PolarSystemPoint
import os
import logging
import math
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GraphService: 
    def __init__(self): 
        self.save_path = os.path.expanduser('~/output/polar.png')
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        
    def create_graph(self, points: list[PolarSystemPoint]): 
        validated_data = self.validate_points(points)
        
        fig = plt.figure(figsize=(6,6))
        ax = fig.add_subplot(111, polar=True)
        colors = ['blue', 'red', 'green', 'orange', 'purple', 
              'brown', 'pink', 'gray', 'olive', 'cyan']
        
        for (tws, twa_dict), color in zip(validated_data.items(), colors):
            twa_rad = sorted(twa_dict.keys())
            speeds = [twa_dict[rad] for rad in twa_rad]
            twa_smooth, speeds_smooth = self.interpolate_linear(twa_rad, speeds) 
            
            ax.plot(twa_smooth, speeds_smooth, 
                    color=color, linewidth=1, 
                    label=f'TWS = {tws} knots')
        
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_rticks(range(5, 20, 5))
        ax.grid(True)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        
        plt.savefig(self.save_path, dpi=300, bbox_inches='tight')
        plt.close()  
        
        return self.save_path
    
    def interpolate_linear(self, twa_rad, speeds, num_points=100):
        if len(twa_rad) < 2:
            return twa_rad, speeds
        
        twa_rad_closed = list(twa_rad) 
        speeds_closed = list(speeds) 
        
        twa_rad_smooth = np.linspace(twa_rad_closed[0], twa_rad_closed[-1], num_points)
        speeds_smooth = np.interp(twa_rad_smooth, twa_rad_closed, speeds_closed)
        speeds_smooth = np.maximum(speeds_smooth, 0)
        
        return twa_rad_smooth.tolist(), speeds_smooth.tolist()
        
    def validate_points(self, points: list[PolarSystemPoint]): 
        points = sorted(points, key=lambda x: x.twa)
        
        validated_points = defaultdict(dict)
        
        for point in points: 
            twa = math.radians(point.twa)
            tws = point.tws    
            bs = point.boat_speed
                        
            validated_points[tws][twa] = (validated_points[tws].get(twa, bs) + bs) / 2
        
        return validated_points