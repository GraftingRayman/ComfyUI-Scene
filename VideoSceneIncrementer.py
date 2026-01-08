import torch

class VideoSceneIncrementer:
    def __init__(self):
        self.current_value = None
        self.last_end = None
        self.last_direction = None
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "start": ("INT", {
                    "default": 0,
                    "min": -100000,
                    "max": 100000,
                    "step": 1
                }),
                "end": ("INT", {
                    "default": 10,
                    "min": -100000,
                    "max": 100000,
                    "step": 1
                }),
                "direction": (["increment", "decrement"],),
                "reset": (["no", "yes"], {"default": "no"}),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("value",)
    FUNCTION = "step"
    CATEGORY = "utils"

    def step(self, start, end, direction, reset, seed):
        # Handle reset
        if reset == "yes":
            self.current_value = start
            self.last_end = end
            self.last_direction = direction
            return (self.current_value,)
        
        # Initialize on first run
        if self.current_value is None:
            self.current_value = start
            self.last_end = end
            self.last_direction = direction
        
        # Check if parameters changed (might want to reset)
        if end != self.last_end or direction != self.last_direction:
            self.current_value = start
            self.last_end = end
            self.last_direction = direction
        
        # Update based on direction
        if direction == "increment":
            self.current_value += 1
            if self.current_value > end:
                self.current_value = end
        else:  # decrement
            self.current_value -= 1
            if self.current_value < end:
                self.current_value = end
        
        return (self.current_value,)

NODE_CLASS_MAPPINGS = {
    "VideoSceneIncrementer": VideoSceneIncrementer
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneIncrementer": "Video Scene Incrementer"
}