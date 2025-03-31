import random
import sys
import numpy as np
from glm import ivec2, ivec3
from gdpc import __url__, Editor, Block, Box, Transform
from gdpc.exceptions import InterfaceConnectionError, BuildAreaNotSetError
from gdpc.vector_tools import addY, dropY
from gdpc.transform import rotatedBoxTransform, flippedBoxTransform
from gdpc.geometry import placeBox, placeCheckeredBox

# Create an editor object.
editor = Editor(buffering=True)

# Check if the editor can connect to the GDMC HTTP interface.
try:
    editor.checkConnection()
except InterfaceConnectionError:
    print(
        f"Error: Could not connect to the GDMC HTTP interface at {editor.host}!\n"
        "To use GDPC, you need to use a \"backend\" that provides the GDMC HTTP interface.\n"
        "For example, by running Minecraft with the GDMC HTTP mod installed.\n"
        f"See {__url__}/README.md for more information."
    )
    sys.exit(1)

# Get the build area.
try:
    buildArea = editor.getBuildArea()
except BuildAreaNotSetError:
    print(
        "Error: failed to get the build area!\n"
        "Make sure to set the build area with the /setbuildarea command in-game.\n"
        "For example: /setbuildarea ~0 0 ~0 ~64 200 ~64"
    )
    sys.exit(1)

#Define build area and heightmap
buildRect = buildArea.toRect()
worldSlice = editor.loadWorldSlice(buildRect)
heightmap = worldSlice.heightmaps["MOTION_BLOCKING_NO_LEAVES"]

#Function which finds and returns the co-ordinates for the most optimal area found
def find_optimal_building_spot(editor, buildRect, heightmap, area_size=(15, 15), step_size=15):#Decreasing step_size will make the search more thorough but come at the cost of computational power
    optimal_coords = None
    lowest_variance = float('inf')

    # Define the area bounds
    max_x = buildRect.end.x - area_size[0] + 1
    max_z = buildRect.end.y - area_size[1] + 1

    # Scan the area with the specified step size
    for x in range(buildRect.begin.x, max_x, step_size):
        for z in range(buildRect.begin.y, max_z, step_size):
            heights = []
            water_found = False
            for xi in range(x, x + area_size[0]):
                for zi in range(z, z + area_size[1]):
                    local_x = xi - buildRect.begin.x
                    local_z = zi - buildRect.begin.y

                    # stay within the heightmap bounds
                    if 0 <= local_x < heightmap.shape[0] and 0 <= local_z < heightmap.shape[1]:
                        y = heightmap[local_x, local_z] - 1  # Use y = height - 1 for the actual ground block
                        block = editor.getBlock((xi, y, zi))
                        #Check and exclude any area where water is found
                        if block == Block("minecraft:water", {"level": "0"}):
                            water_found = True
                            break
                        heights.append(y)
                if water_found:
                    break

            if water_found or not heights:
                continue

            # Calculate the variance of heights
            variance = np.var(heights)

            # Update optimal coordinates and variance if this area is better
            if variance < lowest_variance:
                lowest_variance = variance
                optimal_coords = (x, z)

    return optimal_coords, lowest_variance

import matplotlib.pyplot as plt
import numpy as np

# Assuming `heightmap` is your numpy array representing the terrain height at each point

# Your code for find_optimal_building_spot, flatten_build_area, etc.

#function to generate variance data for plotting
def generate_variance_map(buildRect, heightmap, step_size=15, area_size=(15, 15)):
    variance_map = np.zeros((buildRect.size.y // step_size, buildRect.size.x // step_size))
    for x in range(0, buildRect.size.x - area_size[0] + 1, step_size):
        for z in range(0, buildRect.size.y - area_size[1] + 1, step_size):
            # Calculate variance for each area and assign it to the variance map
            sub_area = heightmap[z:z+area_size[1], x:x+area_size[0]]
            variance = np.var(sub_area)
            variance_map[z // step_size, x // step_size] = variance
    return variance_map

# Example usage
variance_map = generate_variance_map(buildRect, heightmap)

# Plotting the variance map
plt.imshow(variance_map, cmap='viridis', interpolation='nearest')
plt.colorbar(label='Variance')
plt.title('Terrain Variance Evaluation')
plt.xlabel('X Coordinate / Step Size')
plt.ylabel('Z Coordinate / Step Size')
plt.show()

def flatten_build_area(editor, buildRect, heightmap, optimal_coords, area_size=(15, 15)):
    # Calculate local start points for optimal area within heightmap
    local_start_x = optimal_coords[0] - buildRect.begin.x
    local_start_z = optimal_coords[1] - buildRect.begin.y
    #Make temporary heightmap to account for clearing leaves
    heightmapleaves = worldSlice.heightmaps["MOTION_BLOCKING"]

    # Collect heights within the optimal area for the average
    heights = []
    for x in range(local_start_x, local_start_x + area_size[0]):
        for z in range(local_start_z, local_start_z + area_size[1]):
            if 0 <= x < heightmap.shape[0] and 0 <= z < heightmap.shape[1]:
                heights.append(heightmap[x, z] - 1)# Subtracting 1 from y-coordinate to get the actual ground block

    # Calculate the average height
    average_height = int(np.mean(heights))

    # Flatten the area based on the average height
    for x in range(optimal_coords[0], optimal_coords[0] + area_size[0]):
        for z in range(optimal_coords[1], optimal_coords[1] + area_size[1]):
            global_x = x
            global_z = z
            local_x = x - buildRect.begin.x
            local_z = z - buildRect.begin.y
            current_height = heightmap[local_x, local_z] - 1
            current_height_leaves = heightmapleaves[local_x, local_z] - 1

            # Remove blocks above the average height
            if current_height_leaves > average_height:
                for y in range(average_height + 1, 256):
                    editor.placeBlock((global_x, y, global_z), Block("minecraft:air"))

            # Fill in blocks below the average height
            elif current_height < average_height:
                for y in range(current_height + 1, average_height + 1):
                    editor.placeBlock((global_x, y, global_z), Block("minecraft:dirt"))

    #Create a floor for build area of random wood type
    wood_type = ["spruce_planks", "oak_planks", "birch_planks", "dark_oak_planks"]
    wood_choice = random.choice(wood_type)
    for x in range(optimal_coords[0], optimal_coords[0] + area_size[0]):
        for z in range(optimal_coords[1], optimal_coords[1] + area_size[1]):
            global_x = x
            global_z = z
            editor.placeBlock((global_x, average_height, global_z), Block(wood_choice))

    return average_height

#Function which will place a wall
def place_wall_segment(x, z, height, block_type):
    for y_offset in range(height):
        editor.placeBlock((x, flattest_area_offset[1] + y_offset, z), block_type)

#Function to get the correct way for stairs to face based on orientation
def get_stair_facing(x, z, midpoint, orientation):
    facing_direction = None
    if orientation:  # Length along x-axis
        if x < midpoint:  # Ascending
            facing_direction = "east"
        elif x > midpoint:  # Descending
            facing_direction = "west"
    else:  # Length along z-axis
        if z < midpoint:  # Ascending
            facing_direction = "south"
        elif z > midpoint:  # Descending
            facing_direction = "north"

    return facing_direction

#Function to determine how high each roof block should be based on its given position
def calculate_slope_height(position, start_point, max_height, midpoint):
    if even_dimension:
        if position < midpoint:
            return (position - start_point) * slope_height_increase_per_block
        else:
            return ((max_height - (position - midpoint) * slope_height_increase_per_block)-1)
    else:
        if position < midpoint:
            return (position - start_point) * slope_height_increase_per_block
        else:
            return max_height - (position - midpoint) * slope_height_increase_per_block

#Function to determine which direction door should face based on the orientation
def find_door_positions(start_x, start_z, length, orientation, wall_height):
    door_positions = []

    if orientation:  # Wall runs along the x-axis
        middle_x = start_x + length // 2  # Middle for both even and odd widths
        if length % 2 == 0:  # Adjust for even width to move one step left
            middle_x -= 1

        # Positions for the bottom two rows in the middle of the wall
        for y_offset in range(2):  # Door height
            door_positions.append((middle_x, start_z, wall_height + y_offset))
            if length % 2 == 0:  # For even widths, add a second door
                door_positions.append((middle_x + 1, start_z, wall_height + y_offset))

    else:  # Wall runs along the z-axis
        middle_z = start_z + length // 2  # Middle for both even and odd widths
        if length % 2 == 0:  # Adjust for even width to move one step up
            middle_z -= 1

        # Positions for the bottom two rows in the middle of the wall
        for y_offset in range(2):  # Door height
            door_positions.append((start_x, middle_z, wall_height + y_offset))
            if length % 2 == 0:  # For even widths, add a second door
                door_positions.append((start_x, middle_z + 1, wall_height + y_offset))

    return door_positions

#Call function to get optimal co-ords
print(f"Searching for optimal build area...")
optimal_spot, variance = find_optimal_building_spot(editor, buildRect, heightmap)
variance_threshold = 10.0 #PLEASE ALTER VALUE TO PREFERENCE FOR EXPERIMENTATION
#If variance is too high or no area without water is found, program ends and advises user to find another build area to test
if optimal_spot:
    if variance < variance_threshold:
        print(f"Optimal building spot found at: {optimal_spot} with variance: {variance}")
        #if build area is found and suitable, flattening function is called which will return the average height which will be floor for the house
        base_height = flatten_build_area(editor, buildRect, heightmap, optimal_spot)
        print(f"Base height for building after flattening: {base_height}")
    else:
        print(f"No optimal build area found. Area with lowest variance: {variance}, exceeds acceptable threshold. Please try a new build area")
        sys.exit(1)
else:
    print("No suitable building area found due to too much water. Please try a new build area")
    sys.exit(1)

generate_variance_map(buildRect, heightmap)
#Using the optimal build area and average height to create a new build area for the house
flattest_area_offset = (optimal_spot[0], base_height + 1, optimal_spot[1])
MAX_HOUSE_SIZE = Box(flattest_area_offset, (15, 20, 15))
buildRect2 = MAX_HOUSE_SIZE.toRect()
worldSlice2 = editor.loadWorldSlice(buildRect2)
heightmap2 = worldSlice2.heightmaps["MOTION_BLOCKING_NO_LEAVES"]


wall_height_options = [5, 7] #Possible heights for house
length_options = [6, 7]  # Possible lengths x or z dimension of house
width = 9  # Always same width for the alternate dimension
orientation = random.choice([True, False]) #Chooses randomly if house is oriented along x or z axis
length = random.choice(length_options)
wall_height = random.choice(wall_height_options)

if orientation:  # Length along x-axis
    max_start_x = buildRect2.end.x - length
    max_start_z = buildRect2.end.y - width
else:  # Length along z-axis, length and width roles swapped
    max_start_x = buildRect2.end.x - width
    max_start_z = buildRect2.end.y - length

# Ensure start points are within bounds
start_x = random.randint(buildRect2.begin.x, max_start_x)
start_z = random.randint(buildRect2.begin.y, max_start_z)

print("Building walls...")
# Build the walls based on the orientation and random starting point
for i in range(length if orientation else width):
    place_wall_segment(start_x + i, start_z, wall_height, Block("spruce_planks"))
    place_wall_segment(start_x + i, start_z + (width if orientation else length) - 1, wall_height, Block("spruce_planks"))

for i in range(width if orientation else length):
    place_wall_segment(start_x, start_z + i, wall_height, Block("spruce_planks"))
    place_wall_segment(start_x + (length if orientation else width) - 1, start_z + i, wall_height, Block("spruce_planks"))

# Calculate the end points based on the start points and dimensions
end_x = start_x + (length if orientation else width)
end_z = start_z + (width if orientation else length)

# Define buildRect3 for interior use
HOUSE_AREA = Box((start_x, flattest_area_offset[1], start_z), (end_x - start_x, wall_height, end_z - start_z))
buildRect3 = HOUSE_AREA.toRect()
even_dimension = length % 2 == 0

#Build log pillars on each corner of house
for y in range(HOUSE_AREA.begin.y, HOUSE_AREA.end.y):
    editor.placeBlock((HOUSE_AREA.begin.x, y, HOUSE_AREA.begin.z), Block("spruce_log"))
    editor.placeBlock((HOUSE_AREA.begin.x, y, HOUSE_AREA.last.z), Block("spruce_log"))
    editor.placeBlock((HOUSE_AREA.last.x, y, HOUSE_AREA.begin.z), Block("spruce_log"))
    editor.placeBlock((HOUSE_AREA.last.x, y, HOUSE_AREA.last.z), Block("spruce_log"))

print("building walls done")
(print("placing doors..."))
#place the doors
wall_height = HOUSE_AREA.size.y
midpoint = None
# Determine the direction to slope
if orientation:  # If length is along the x-axis
    midpoint = (HOUSE_AREA.end.x + HOUSE_AREA.begin.x) // 2
else:  # If length is along the z-axis
    midpoint = (HOUSE_AREA.end.z + HOUSE_AREA.begin.z) // 2

if orientation:
    if even_dimension:
        editor.placeBlock((midpoint - 1, HOUSE_AREA.begin.y, HOUSE_AREA.begin.z), Block("dark_oak_door", {"facing": "south", "hinge": "right"}))
        editor.placeBlock((midpoint, HOUSE_AREA.begin.y, HOUSE_AREA.begin.z), Block("dark_oak_door", {"facing": "south", "hinge": "left"}))

    else:
        editor.placeBlock((midpoint, HOUSE_AREA.begin.y, HOUSE_AREA.begin.z), Block("dark_oak_door", {"facing": "south", "hinge": "right"}))

else:
    if even_dimension:
        editor.placeBlock((HOUSE_AREA.begin.x, HOUSE_AREA.begin.y, midpoint - 1), Block("dark_oak_door", {"facing": "east", "hinge": "left"}))
        editor.placeBlock((HOUSE_AREA.begin.x, HOUSE_AREA.begin.y, midpoint), Block("dark_oak_door", {"facing": "east", "hinge": "right"}))

    else:
        editor.placeBlock((HOUSE_AREA.begin.x, HOUSE_AREA.begin.y, midpoint), Block("dark_oak_door", {"facing": "east", "hinge": "right"}))

print("placing walls done")

#Place roof
print("Building roof...")

slope_height_increase_per_block = 1

# Calculate the starting height for the roof
starting_roof_height = flattest_area_offset[1] + wall_height
max_slope_height = None

# Determine the direction to slope (up to the midpoint)
if orientation:  # If length is along the x-axis
    max_slope_height = (midpoint - HOUSE_AREA.begin.x) * slope_height_increase_per_block
else:  # If length is along the z-axis
    max_slope_height = (midpoint - HOUSE_AREA.begin.z) * slope_height_increase_per_block

# Build the roof out of random material
roof_options = ["deepslate_brick_stairs", "polished_diorite_stairs", "brick_stairs"]
roof_type = random.choice(roof_options)
plateau_options =["polished_diorite_slab", "deepslate_brick_slab"]
plateau = random.choice(plateau_options)
for x in range(((HOUSE_AREA.begin.x)-1), ((HOUSE_AREA.end.x)+1)):
    for z in range(((HOUSE_AREA.begin.z)-1), ((HOUSE_AREA.end.z)+1)):
        if orientation:
            slope_height = calculate_slope_height(x, HOUSE_AREA.begin.x, max_slope_height, midpoint)
        else:
            slope_height = calculate_slope_height(z, HOUSE_AREA.begin.z, max_slope_height, midpoint)

        roof_height = flattest_area_offset[1] + wall_height + slope_height

        if even_dimension:
            if orientation:
                if x == midpoint - 1 or x == midpoint:
                    roof_block_type = Block(plateau)
                    editor.placeBlock((x, roof_height, z), roof_block_type)

                elif x < midpoint:
                    stair_direction = get_stair_facing(x, z, midpoint, orientation)
                    roof_block_type = Block(roof_type, {"facing": stair_direction})
                    editor.placeBlock((x, roof_height, z), roof_block_type)

                else:
                    stair_direction = get_stair_facing(x, z, midpoint, orientation)
                    roof_block_type = Block(roof_type, {"facing": stair_direction})
                    editor.placeBlock((x, roof_height, z), roof_block_type)

            else:
                if z == midpoint -1 or z == midpoint:
                    roof_block_type = Block(plateau)
                    editor.placeBlock((x, roof_height, z), roof_block_type)

                elif z < midpoint:
                    stair_direction = get_stair_facing(x, z, midpoint, orientation)
                    roof_block_type = Block(roof_type, {"facing": stair_direction})
                    editor.placeBlock((x, roof_height, z), roof_block_type)

                else:
                    stair_direction = get_stair_facing(x, z, midpoint, orientation)
                    roof_block_type = Block(roof_type, {"facing": stair_direction})
                    editor.placeBlock((x, roof_height, z), roof_block_type)

        else:
            if orientation:
                if x < midpoint:
                    stair_direction = get_stair_facing(x, z, midpoint, orientation)
                    roof_block_type = Block(roof_type, {"facing": stair_direction})
                    editor.placeBlock((x, roof_height, z), roof_block_type)
                elif x == midpoint:
                    roof_block_type = Block(plateau)
                    editor.placeBlock((x, roof_height, z), roof_block_type)
                else:
                    stair_direction = get_stair_facing(x, z, midpoint, orientation)
                    roof_block_type = Block(roof_type, {"facing": stair_direction})
                    editor.placeBlock((x, roof_height, z), roof_block_type)

            else:
                if z < midpoint:
                    stair_direction = get_stair_facing(x, z, midpoint, orientation)
                    roof_block_type = Block(roof_type, {"facing": stair_direction})
                    editor.placeBlock((x, roof_height, z), roof_block_type)
                elif z == midpoint:
                    roof_block_type = Block(plateau)
                    editor.placeBlock((x, roof_height, z), roof_block_type)
                else:
                    stair_direction = get_stair_facing(x, z, midpoint, orientation)
                    roof_block_type = Block(roof_type, {"facing": stair_direction})
                    editor.placeBlock((x, roof_height, z), roof_block_type)


interior_floor_level = flattest_area_offset[1]
interior_ceiling_level = flattest_area_offset[1] + wall_height
print("Building roof done")

#GLASS windows at roof
ceiling_height = interior_ceiling_level + 2
if orientation:
    if even_dimension:
        internal_start_x = start_x + 1  # One block inward from the starting Z position of the wall
        internal_end_x = start_x + length - 1

        for i in range(internal_start_x, internal_end_x):
            editor.placeBlock((i, interior_ceiling_level, HOUSE_AREA.begin.z), Block("glass"))
            editor.placeBlock((i, interior_ceiling_level, HOUSE_AREA.last.z), Block("glass"))

        for i in range(internal_start_x + 1, internal_end_x - 1):
            editor.placeBlock((i, interior_ceiling_level + 1, HOUSE_AREA.begin.z), Block("glass"))
            editor.placeBlock((i, interior_ceiling_level + 1, HOUSE_AREA.last.z), Block("glass"))

    else:
        internal_start_x = start_x + 1
        internal_end_x = start_x + length - 1

        for i in range(internal_start_x, internal_end_x):
            editor.placeBlock((i, interior_ceiling_level, HOUSE_AREA.begin.z), Block("glass"))
            editor.placeBlock((i, interior_ceiling_level, HOUSE_AREA.last.z), Block("glass"))

        for i in range(internal_start_x + 1, internal_end_x - 1):
            editor.placeBlock((i, interior_ceiling_level + 1, HOUSE_AREA.begin.z), Block("glass"))
            editor.placeBlock((i, interior_ceiling_level + 1, HOUSE_AREA.last.z), Block("glass"))

        editor.placeBlock((internal_start_x + 2, interior_ceiling_level + 2, HOUSE_AREA.begin.z), Block("glass"))
        editor.placeBlock((internal_start_x + 2, interior_ceiling_level + 2, HOUSE_AREA.last.z), Block("glass"))

else:
    if even_dimension:
        internal_start_z = start_z + 1
        internal_end_z = start_z + length - 1

        for i in range(internal_start_z, internal_end_z):
            editor.placeBlock((HOUSE_AREA.begin.x, interior_ceiling_level, i), Block("glass"))
            editor.placeBlock((HOUSE_AREA.last.x, interior_ceiling_level, i), Block("glass"))

        for i in range(internal_start_z + 1, internal_end_z - 1):
            editor.placeBlock((HOUSE_AREA.begin.x, interior_ceiling_level + 1, i), Block("glass"))
            editor.placeBlock((HOUSE_AREA.last.x, interior_ceiling_level + 1, i), Block("glass"))

    else:
        internal_start_z = start_z + 1
        internal_end_z = start_z + length - 1

        for i in range(internal_start_z, internal_end_z):
            editor.placeBlock((HOUSE_AREA.begin.x, interior_ceiling_level, i), Block("glass"))
            editor.placeBlock((HOUSE_AREA.last.x, interior_ceiling_level, i), Block("glass"))

        for i in range(internal_start_z + 1, internal_end_z - 1):
            editor.placeBlock((HOUSE_AREA.begin.x, interior_ceiling_level + 1, i), Block("glass"))
            editor.placeBlock((HOUSE_AREA.last.x, interior_ceiling_level + 1, i), Block("glass"))

        editor.placeBlock((HOUSE_AREA.begin.x, interior_ceiling_level + 2, internal_start_z + 2), Block("glass"))
        editor.placeBlock((HOUSE_AREA.last.x, interior_ceiling_level + 2, internal_start_z + 2), Block("glass"))

print("Filling interior...")
# LANTERN always at top of roof and a two random opposite corners
if orientation:
    internal_start_z = start_z + 2
    internal_end_z = start_z + width - 2
    internal_start_x = start_x + 2
    internal_end_x = start_x + length - 2
    editor.placeBlock((internal_start_x - 1, interior_ceiling_level, internal_start_z - 1), Block("lantern", {"hanging": "true"}))
    editor.placeBlock((internal_end_x, interior_ceiling_level, internal_end_z), Block("lantern", {"hanging": "true"}))
    if even_dimension:

        item_placement_height = interior_ceiling_level + 1
        rand_z_cord = random.randint(internal_start_z, internal_end_z)
        editor.placeBlock((midpoint, item_placement_height, rand_z_cord), Block("lantern", {"hanging": "true"}))

    else:

        item_placement_height = interior_ceiling_level + 2
        rand_z_cord = random.randint(internal_start_z, internal_end_z)
        editor.placeBlock((midpoint, item_placement_height, rand_z_cord), Block("lantern", {"hanging": "true"}))


else:
    internal_start_z = start_z + 2
    internal_end_z = start_z + length - 2
    internal_start_x = start_x + 2
    internal_end_x = start_x + width - 2
    editor.placeBlock((internal_start_x - 1, interior_ceiling_level, internal_start_z - 1),Block("lantern", {"hanging": "true"}))
    editor.placeBlock((internal_end_x, interior_ceiling_level, internal_end_z), Block("lantern", {"hanging": "true"}))

    if even_dimension:

        item_placement_height = interior_ceiling_level + 1
        rand_x_cord = random.randint(internal_start_x, internal_end_x)
        editor.placeBlock((rand_x_cord, item_placement_height, midpoint), Block("lantern", {"hanging": "true"}))

    else:

        item_placement_height = interior_ceiling_level + 2
        rand_x_cord = random.randint(internal_start_x, internal_end_x)
        editor.placeBlock((rand_x_cord, item_placement_height, midpoint), Block("lantern", {"hanging": "true"}))

#Bed
bed_colour_options = ["white_bed", "black_bed", "red_bed", "blue_bed", "lime_bed"]
bed_colour = random.choice(bed_colour_options)
if orientation:
    internal_start_z = start_z + 2
    internal_end_z = start_z + width - 2
    internal_start_x = start_x + 2
    internal_end_x = start_x + length - 2
    bed_position_options = [internal_start_x - 1, internal_end_x]
    bed_position = random.choice(bed_position_options)
    editor.placeBlock((bed_position, HOUSE_AREA.begin.y, HOUSE_AREA.end.z - 3), Block(bed_colour, {"facing": "south"}))

#Placing rest of interior with relation to the bed to ensure consistency and randomness
    if bed_position == internal_start_x - 1:
        item_position = internal_end_x
        rand_z_cord_ct = random.randint(internal_start_z, internal_end_z)
        editor.placeBlock((item_position, HOUSE_AREA.begin.y, rand_z_cord_ct), Block("crafting_table"))
        rand_z_cord_f = random.randint(internal_start_z, internal_end_z)
        while rand_z_cord_f == rand_z_cord_ct:
            rand_z_cord_f = random.randint(internal_start_z, internal_end_z)
        editor.placeBlock((item_position, HOUSE_AREA.begin.y, rand_z_cord_f), Block("furnace"))
        rand_z_cord_ch = random.randint(internal_start_z, internal_end_z)
        while rand_z_cord_ch == rand_z_cord_f or rand_z_cord_ch == rand_z_cord_ct:
            rand_z_cord_ch = random.randint(internal_start_z, internal_end_z)
        editor.placeBlock((item_position, HOUSE_AREA.begin.y, rand_z_cord_ch), Block("chest"))
    else:
        item_position = internal_start_x - 1
        rand_z_cord_ct = random.randint(internal_start_z, internal_end_z)
        editor.placeBlock((item_position, HOUSE_AREA.begin.y, rand_z_cord_ct), Block("crafting_table"))
        rand_z_cord_f = random.randint(internal_start_z, internal_end_z)
        while rand_z_cord_f == rand_z_cord_ct:
            rand_z_cord_f = random.randint(internal_start_z, internal_end_z)
        editor.placeBlock((item_position, HOUSE_AREA.begin.y, rand_z_cord_f), Block("furnace"))
        rand_z_cord_ch = random.randint(internal_start_z, internal_end_z)
        while rand_z_cord_ch == rand_z_cord_f or rand_z_cord_ch == rand_z_cord_ct:
            rand_z_cord_ch = random.randint(internal_start_z, internal_end_z)
        editor.placeBlock((item_position, HOUSE_AREA.begin.y, rand_z_cord_ch), Block("chest"))

else:
    internal_start_x = start_x + 2
    internal_end_x = start_x + width - 2
    internal_start_z = start_z + 2  # One block inward from the starting Z position of the wall
    internal_end_z = start_z + length - 2

    bed_position_options = [internal_start_z - 1, internal_end_z]
    bed_position = random.choice(bed_position_options)
    editor.placeBlock((HOUSE_AREA.end.x - 3, HOUSE_AREA.begin.y, bed_position), Block(bed_colour, {"facing": "east"}))

    if bed_position == internal_start_z - 1:
        item_position = internal_end_z
        rand_x_cord_ct = random.randint(internal_start_x, internal_end_x)
        editor.placeBlock((rand_x_cord_ct, HOUSE_AREA.begin.y, item_position), Block("crafting_table"))
        rand_x_cord_f = random.randint(internal_start_x, internal_end_x)
        while rand_x_cord_f == rand_x_cord_ct:
            rand_x_cord_f = random.randint(internal_start_x, internal_end_x)
        editor.placeBlock((rand_x_cord_f, HOUSE_AREA.begin.y, item_position), Block("furnace"))
        rand_x_cord_ch = random.randint(internal_start_x, internal_end_x)
        while rand_x_cord_ch == rand_x_cord_f or rand_x_cord_ch == rand_x_cord_ct:
            rand_x_cord_ch = random.randint(internal_start_x, internal_end_x)
        editor.placeBlock((rand_x_cord_ch, HOUSE_AREA.begin.y, item_position), Block("chest"))
    else:
        item_position = internal_start_z - 1
        rand_x_cord_ct = random.randint(internal_start_x, internal_end_x)
        editor.placeBlock((rand_x_cord_ct, HOUSE_AREA.begin.y, item_position), Block("crafting_table"))
        rand_x_cord_f = random.randint(internal_start_x, internal_end_x)
        while rand_x_cord_f == rand_x_cord_ct:
            rand_x_cord_f = random.randint(internal_start_x, internal_end_x)
        editor.placeBlock((rand_x_cord_f, HOUSE_AREA.begin.y, item_position), Block("furnace"))
        rand_x_cord_ch = random.randint(internal_start_x, internal_end_x)
        while rand_x_cord_ch == rand_x_cord_f or rand_x_cord_ch == rand_x_cord_ct:
            rand_x_cord_ch = random.randint(internal_start_x, internal_end_x)
        editor.placeBlock((rand_x_cord_ch, HOUSE_AREA.begin.y, item_position), Block("chest"))

print("Interior complete")
print(f"Your log cabin has successfully been built at X:{optimal_spot[0]} and Z:{optimal_spot[1]} with an average height of {base_height}")