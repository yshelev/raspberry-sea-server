import matplotlib.pyplot as plt
from collections import defaultdict
from models.PolarSystemPoint import PolarSystemPoint
import os
import logging
import math
import numpy as np
from scipy.interpolate import Akima1DInterpolator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TWA_BIN_STEP = 5
class GraphService: 
    def __init__(self): 
        self.save_path = os.path.expanduser('~/output/polar.png')
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        
    def create_graph(self, points: list[PolarSystemPoint]):
        logger.info(f"create_graph: получено {len(points)} точек")
        validated_data = self.validate_points(points)
        
        fig = plt.figure(figsize=(6,6))
        ax = fig.add_subplot(111, polar=True)
        colors = ['blue', 'red', 'green', 'orange', 'purple', 
              'brown', 'pink', 'gray', 'olive', 'cyan']
        
        for (tws, twa_dict), color in zip(sorted(validated_data.items()), colors):
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
        wind_zones = [
            (math.radians(3), 'Левентик'),
            (math.radians(68), 'Бейдевинд'),
            (math.radians(95), 'Галфвинд'),
            (math.radians(135), 'Бакштаг'),
            (math.radians(165), 'Фордевинд'),
        ]

        r_max = ax.get_rmax()
        for angle_rad, label in wind_zones:
            ax.text(angle_rad, r_max * 1.17, label,
                    ha='center', va='center',
                    fontsize=9, color='#444',
                    rotation=0)
        
        plt.savefig(self.save_path, dpi=300, bbox_inches='tight')
        plt.close()  
        
        return self.save_path


    def interpolate_linear(self, twa_rad, speeds, num_points=100):
        if len(twa_rad) < 2:
            return twa_rad, speeds

        if len(twa_rad) < 4:
            twa_smooth = np.linspace(twa_rad[0], twa_rad[-1], num_points)
            speeds_smooth = np.interp(twa_smooth, twa_rad, speeds)
            return twa_smooth.tolist(), np.maximum(speeds_smooth, 0).tolist()

        twa_arr = np.array(twa_rad)
        speeds_arr = np.array(speeds)

        akima = Akima1DInterpolator(twa_arr, speeds_arr)

        twa_smooth = np.linspace(twa_arr[0], twa_arr[-1], num_points)
        speeds_smooth = akima(twa_smooth)
        speeds_smooth = np.maximum(speeds_smooth, 0)

        return twa_smooth.tolist(), speeds_smooth.tolist()

    def validate_points(self, points: list[PolarSystemPoint]):
        points = sorted(points, key=lambda x: x.twa)

        sums = defaultdict(lambda: defaultdict(float))
        counts = defaultdict(lambda: defaultdict(int))

        for point in points:
            # Группируем TWA в бины по 5°
            twa_bin = round(point.twa / TWA_BIN_STEP) * TWA_BIN_STEP
            twa = math.radians(twa_bin)
            tws = point.tws
            bs = point.boat_speed

            sums[tws][twa] += bs
            counts[tws][twa] += 1

        validated_points = defaultdict(dict)
        for tws, twa_dict in sums.items():
            for twa, total in twa_dict.items():
                validated_points[tws][twa] = total / counts[tws][twa]

        return validated_points