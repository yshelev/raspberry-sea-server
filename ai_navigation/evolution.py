import json
import math
import random
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from simulator import SailboatSimulator, WindModel
from polar_diagram import racing_polar

CONFIG = {
    # Amur Bay, Vladivostok
    "start_lat":  43.109061,
    "start_lon":  131.865189,
    "checkpoints": [
        (43.109061, 131.865189),
        (43.105771, 131.854926),
        (43.099269, 131.846082),
        (43.105075, 131.836234),
        (43.108750, 131.847743),
        (43.110079, 131.862413),
    ],

    "wind_tws": 16.0,
    "wind_twd": 90.0,

    "wind_twd_sigma": 4.0,
    "wind_tws_sigma": 0.8,
    "wind_twd_alpha": 0.03,
    "wind_tws_alpha": 0.05,

    "eval_scenarios": [
        (   0,   0),
        # ( +45,  +4),
        # ( -45,  -4),
        # (+135,   0),
        # (   0,  -8),
    ],

    "generations":       50,
    "population_size":   80,
    "elite_count":       10,
    "tournament_k":      5,
    "mutation_rate":     0.15,
    "mutation_strength": 0.4,
    "crossover_prob":    0.6,
    "max_steps":         15_000,

    "input_size":  7,
    "hidden_size": 8,
    "output_size": 1,

    "save_dir": ".",
}


class NeuralNetwork:

    def __init__(self, input_size=6, hidden_size=8, output_size=1):
        self.input_size  = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size

        w1_size = hidden_size * input_size
        b1_size = hidden_size
        w2_size = output_size * hidden_size
        b2_size = output_size
        self._n = w1_size + b1_size + w2_size + b2_size

        params = np.concatenate([
            np.random.randn(w1_size) * math.sqrt(2.0 / input_size),
            np.zeros(b1_size),
            np.random.randn(w2_size) * math.sqrt(2.0 / hidden_size),
            np.zeros(b2_size),
        ])
        self.params = params

        self._shapes = [
            (w1_size,),
            (b1_size,),
            (w2_size,),
            (b2_size,),
        ]
        self._sizes = [w1_size, b1_size, w2_size, b2_size]

    def _split(self):
        idx = np.cumsum([0] + self._sizes)
        W1 = self.params[idx[0]:idx[1]].reshape(self.hidden_size, self.input_size)
        b1 = self.params[idx[1]:idx[2]]
        W2 = self.params[idx[2]:idx[3]].reshape(self.output_size, self.hidden_size)
        b2 = self.params[idx[3]:idx[4]]
        return W1, b1, W2, b2

    def predict(self, obs: np.ndarray) -> float:
        W1, b1, W2, b2 = self._split()
        h = np.tanh(W1 @ obs + b1)
        out = np.tanh(W2 @ h + b2)
        return float(out[0])


    def mutate(self, rate: float, strength: float) -> "NeuralNetwork":
        child = self.copy()
        mask = np.random.rand(self._n) < rate
        child.params[mask] += np.random.randn(mask.sum()) * strength
        return child

    def crossover(self, other: "NeuralNetwork") -> "NeuralNetwork":
        child = self.copy()
        mask = np.random.rand(self._n) < 0.5
        child.params[mask] = other.params[mask]
        return child

    def copy(self) -> "NeuralNetwork":
        net = NeuralNetwork(self.input_size, self.hidden_size, self.output_size)
        net.params = self.params.copy()
        return net

    def save(self, path: str):
        data = {
            "input_size":  self.input_size,
            "hidden_size": self.hidden_size,
            "output_size": self.output_size,
            "params":      self.params.tolist(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "NeuralNetwork":
        with open(path) as f:
            data = json.load(f)
        net = cls(data["input_size"], data["hidden_size"], data["output_size"])
        net.params = np.array(data["params"])
        return net


def _run_episode(net: NeuralNetwork, cfg: dict,
                 wind_twd: float, wind_tws: float) -> tuple[float, int, int]:
    wind_model = WindModel(
        base_twd=wind_twd,
        base_tws=wind_tws,
        twd_sigma=cfg.get("wind_twd_sigma", 0.0),
        tws_sigma=cfg.get("wind_tws_sigma", 0.0),
        twd_alpha=cfg.get("wind_twd_alpha", 0.03),
        tws_alpha=cfg.get("wind_tws_alpha", 0.05),
    )

    sim = SailboatSimulator(polar_function=racing_polar, wind_model=wind_model)
    sim.reset(
        start_lat=cfg["start_lat"],
        start_lon=cfg["start_lon"],
        start_heading=random.uniform(0, 360),
        checkpoints=cfg["checkpoints"],
        wind_tws=wind_tws,
        wind_twd=wind_twd,
        max_steps=cfg["max_steps"],
    )

    total_reward = 0.0
    while not sim.done:
        obs = sim.get_observations()
        action = net.predict(obs)
        _, reward, _ = sim.step(action)
        total_reward += reward

    return total_reward, sim._checkpoints_passed, sim.time_sec

def evaluate(net: NeuralNetwork, cfg: dict) -> tuple[float, int, int]:
    base_twd = cfg["wind_twd"]
    base_tws = cfg["wind_tws"]
    scenarios = cfg.get("eval_scenarios", [(0, 0)])

    rewards = list()
    base_cp = base_time = None

    for i, (delta_twd, delta_tws) in enumerate(scenarios):
        twd = (base_twd + delta_twd) % 360
        tws = float(np.clip(base_tws + delta_tws, 4.0, 30.0))

        reward, cp, t = _run_episode(net, cfg, twd, tws)
        rewards.append(reward)

        if i == 0:
            base_cp, base_time = cp, t

    return float(np.mean(rewards)), base_cp, base_time

def tournament_select(population: list, fitnesses: list, k: int) -> NeuralNetwork:
    idxs = random.sample(range(len(population)), min(k, len(population)))
    best = max(idxs, key=lambda i: fitnesses[i])
    return population[best]

def evolve(cfg: dict = CONFIG) -> NeuralNetwork:
    save_dir = Path(cfg["save_dir"])

    n_cp = len(cfg["checkpoints"])
    pop_size   = cfg["population_size"]
    elite_n    = cfg["elite_count"]
    tourn_k    = cfg["tournament_k"]
    mut_rate   = cfg["mutation_rate"]
    mut_str    = cfg["mutation_strength"]
    cross_prob = cfg["crossover_prob"]
    generations = cfg["generations"]

    population = [
        NeuralNetwork(cfg["input_size"], cfg["hidden_size"], cfg["output_size"])
        for _ in range(pop_size)
    ]

    best_ever: NeuralNetwork | None = None
    best_ever_fitness = float("-inf")

    history = list()

    print("=" * 70)
    print("  SAILBOAT NEURO-EVOLUTION  (variable wind + multi-scenario)")
    print("=" * 70)
    print(f"  Population:  {pop_size}  |  Elite: {elite_n}  |  Generations: {generations}")
    print(f"  Base wind:   {cfg['wind_tws']} kn from {cfg['wind_twd']}°")
    print(f"  Wind noise:  σ_twd={cfg.get('wind_twd_sigma',0)}°  σ_tws={cfg.get('wind_tws_sigma',0)} kn")
    n_sc = len(cfg.get("eval_scenarios", [(0,0)]))
    print(f"  Scenarios:   {n_sc} per agent  (fitness = mean)")
    print(f"  Checkpoints: {n_cp}  |  Max steps: {cfg['max_steps']}")
    print("=" * 70)

    train_start = time.time()

    for gen in range(generations):
        gen_start = time.time()

        results = [evaluate(net, cfg) for net in population]
        fitnesses   = [r[0] for r in results]
        checkpoints = [r[1] for r in results]
        times       = [r[2] for r in results]

        best_idx     = int(np.argmax(fitnesses))
        best_fitness = fitnesses[best_idx]
        best_cp      = checkpoints[best_idx]
        best_time    = times[best_idx]
        avg_fitness  = float(np.mean(fitnesses))
        max_cp       = max(checkpoints)

        history.append((gen, best_fitness, avg_fitness, best_cp, best_time))

        if best_fitness > best_ever_fitness:
            best_ever_fitness = best_fitness
            best_ever = population[best_idx].copy()
            best_ever.save(str(save_dir / "best_network.json"))

        elapsed = time.time() - gen_start
        total_elapsed = (time.time() - train_start) / 60
        finished_mark = " ✅" if best_cp >= n_cp else ""
        print(
            f"Gen {gen:4d}/{generations}"
            f"  fit={best_fitness:9.1f}"
            f"  avg={avg_fitness:9.1f}"
            f"  cp={best_cp}/{n_cp}{finished_mark}"
            f"  t={best_time:6.0f}s"
            f"  max_cp={max_cp}"
            f"  [{elapsed:.1f}s, total {total_elapsed:.1f}min]"
        )

        if len(history) >= 30:
            recent = [h[1] for h in history[-30:]]
            if max(recent) - min(recent) < 200 and best_cp >= n_cp:
                print(f"\nFitness stabilized. Stop.")
                break

        sorted_idx = np.argsort(fitnesses)[::-1]

        new_pop = list()

        for i in range(elite_n):
            new_pop.append(population[sorted_idx[i]].copy())

        adaptive_str = mut_str * (1.0 - 0.7 * gen / generations)

        while len(new_pop) < pop_size:
            parent1 = tournament_select(population, fitnesses, tourn_k)

            if random.random() < cross_prob:
                parent2 = tournament_select(population, fitnesses, tourn_k)
                child = parent1.crossover(parent2)
            else:
                child = parent1.copy()

            child = child.mutate(mut_rate, adaptive_str)
            new_pop.append(child)

        population = new_pop

    total_time = (time.time() - train_start) / 60
    print("\n" + "=" * 70)
    print(f"  DONE  |  Total time: {total_time:.1f} min")
    print(f"  Best fitness:     {best_ever_fitness:.1f}")
    print(f"  Best checkpoints: {history[-1][3]}/{n_cp}")
    print(f"  Saved to:         {save_dir / 'best_network.json'}")
    print("=" * 70)

    _save_history(history, save_dir)

    return best_ever

def test_network(path: str = "best_network.json", cfg: dict = CONFIG, n_runs: int = 5):
    net = NeuralNetwork.load(path)
    n_cp = len(cfg["checkpoints"])

    print(f"\nТестирование {path} ({n_runs} запусков):")
    print("-" * 50)

    for i in range(n_runs):
        fitness, cp, t = _run_episode(net, cfg, cfg["wind_twd"], cfg["wind_tws"])
        status = "✅" if cp >= n_cp else f"cp={cp}/{n_cp}"
        print(f"  Run {i+1}: fitness={fitness:.1f}  time={t}s ({t/60:.1f}min)  {status}")


def cross_validate(path: str = "best_network.json", cfg: dict = CONFIG):
    net = NeuralNetwork.load(path)
    n_cp = len(cfg["checkpoints"])

    print("\nCross validation by wind conditions:")
    print("-" * 50)

    static_cfg = {**cfg, "wind_twd_sigma": 0.0, "wind_tws_sigma": 0.0}

    tests = [
        ("Train wind", cfg["wind_tws"], cfg["wind_twd"]),
        ("Weak wind",        8.0,  cfg["wind_twd"]),
        ("High wind",      22.0,  cfg["wind_twd"]),
        ("TWD +45°",            cfg["wind_tws"],        (cfg["wind_twd"] + 45) % 360),
        ("TWD -45°",            cfg["wind_tws"],        (cfg["wind_twd"] - 45) % 360),
        ("TWD +135°",           cfg["wind_tws"],        (cfg["wind_twd"] + 135) % 360),
    ]

    for label, tws, twd in tests:
        fitness, cp, t = _run_episode(net, static_cfg, twd, tws)
        status = "✅" if cp >= n_cp else f"cp={cp}/{n_cp}"
        print(f"  {label:25s}: fit={fitness:8.1f}  t={t:6.0f}s  {status}")

def _save_history(history, save_dir: Path):
    import csv
    path = save_dir / "training_log.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gen", "best_fitness", "avg_fitness", "best_cp", "best_time_s"])
        w.writerows(history)
    print(f"  Log saved to {path}")


if __name__ == "__main__":
    best = evolve(CONFIG)
    test_network(cfg=CONFIG)
    cross_validate(cfg=CONFIG)
