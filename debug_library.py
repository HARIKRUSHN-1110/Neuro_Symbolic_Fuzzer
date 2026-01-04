# debug_library.py
# this file is for attributes and classes to check weather they are exist in "scenarigeneration" library or not
from scenariogeneration import xosc

print("--- Version Info ---")
try:
    import scenariogeneration #type: ignore
    print(f"Version: {scenariogeneration.__version__}")
except:
    print("Version not found")

print("Searching for 'Performance'")
# List all attributes in xosc
attributes = dir(xosc)
matches = [a for a in attributes if "Performance" in a]
print(f"Found matches: {matches}")

print("Searching for 'Vehicle'")
# see what the Vehicle class expects
import inspect
print(inspect.signature(xosc.Vehicle))