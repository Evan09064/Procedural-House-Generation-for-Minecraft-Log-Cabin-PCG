# Procedural House Generation for Minecraft: Log Cabin PCG

This repository contains a Python-based procedural content generation (PCG) project designed for Minecraft. Using the GDPC library, the project analyzes a designated build area to find optimal building spots, flattens the terrain, and generates unique log cabin designs. This work demonstrates advanced PCG techniques and Game AI expertise in adapting content to varied environments.

## Features

- **Environment Analysis:** Scans the build area to compute height variance and detect water, ensuring only suitable locations are considered.
- **Optimal Building Spot:** Identifies the flattest, water-free 15x15 sub-area within a larger build area for minimal terrain modification.
- **Terrain Flattening:** Computes the average height of the optimal area and adjusts terrain to create a stable foundation.
- **Random House Generation:** Randomizes key design elements including house dimensions, roof style, orientation, and interior placements (bed, chest, crafting table, furnace) to ensure each structure is unique.
- **PCG Techniques:** Balances deterministic optimal placement with controlled randomness to produce believable, adaptive game content.

## Requirements

- Python 3.8+
- GDPC library (refer to [GDPC GitHub](https://github.com/avdstaaij/gdpc) for installation)
- Minecraft (for context; the generation process is independent)

## Usage

To generate a house design, run the main script

This script will:
- Analyze the designated build area,
- Identify the most optimal spot based on terrain flatness and water presence,
- Flatten the selected area, and
- Generate a uniquely randomized log cabin design.

## Experiment Overview

The project showcases how procedural content generation can create diverse and believable game environments by:
- Evaluating terrain for optimal building placement,
- Adapting the environment with minimal modifications,
- Incorporating randomness into architectural design (e.g., varying dimensions and interior arrangements).

## License

[MIT License]
