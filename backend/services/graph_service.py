import matplotlib.pyplot as plt
from collections import defaultdict
from models.PolarSystemPoint import PolarSystemPoint
import os
from pathlib import Path

class GraphService: 
    def __init__(self): 
        self.save_path = os.path.expanduser('~/output/polar.png')
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        
    def create_graph(self, points: list[PolarSystemPoint]): 
        valid_tws, thetas, rs = self.validate_points(points)
        
        theta = thetas[valid_tws]
        r = rs[valid_tws]
        
        fig = plt.figure(figsize=(6,6))
        ax = fig.add_subplot(111, polar=True) 
        ax.plot(theta, r, color='blue', linewidth=2)

        ax.set_rticks([0.5, 1, 1.5, 2]) 
        ax.grid(True)
        
        plt.savefig(self.save_path, dpi=300, bbox_inches='tight')
        
        return self.save_path
        
    def validate_points(self, points: list[PolarSystemPoint]): 
        points = sorted(points, key=lambda x: x.twa)
        
        validated_points_angles = defaultdict(list)
        validated_points_boat_speeds = defaultdict(list)
        
        last_point = None
        
        for point in points: 
            last_point = point.tws
            validated_points_angles[point.tws].append(point.twa)
            validated_points_boat_speeds[point.tws].append(point.boat_speed)
        
        return last_point, dict(validated_points_angles), dict(validated_points_boat_speeds)