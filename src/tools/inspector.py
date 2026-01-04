# src/tools/inspector.py
import inspect
from scenariogeneration import xosc

def get_class_signature(class_name):
    """
    Looks up a class in the xosc library and returns its exact argument list.
    """
    if not hasattr(xosc, class_name):
        return f"Error: Class 'xosc.{class_name}' not found."
    
    cls = getattr(xosc, class_name)
    try:
        # Get the constructor signature
        sig = inspect.signature(cls.__init__)
        # Convert to string and clean up 'self'
        sig_str = str(sig).replace("(self, ", "(").replace("(self)", "()")
        return f"xosc.{class_name}{sig_str}"
    except Exception as e:
        return f"Could not inspect {class_name}: {e}"

if __name__ == "__main__":
    # List of classes causing us trouble
    troublemakers = [
        "RelativeDistanceCondition",
        "EntityTrigger",
        "AbsoluteLaneChangeAction",
        "TransitionDynamics"
    ]
    
    print("\n--- LIBRARY CHEAT SHEET (Copy this to your Prompt) ---")
    for name in troublemakers:
        print(get_class_signature(name))
    print("------------------------------------------------------\n")