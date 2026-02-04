import re

class VideoScenePromptModifier:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "original_prompt": ("STRING", {"multiline": True}),
            },
            "optional": {
                "image_style": (["anime", "photorealistic", "oil painting", "sketch", "watercolor", "digital art", "comic book", "cartoon", "3D render", "cinematic", "keep original"], {"default": "keep original"}),
                "image_lighting": (["natural", "dramatic", "soft", "harsh", "golden hour", "blue hour", "studio", "moody", "backlit", "neon", "keep original"], {"default": "keep original"}),
                "action": ("STRING", {"multiline": True, "default": ""}),
                "action_details": ("STRING", {"multiline": True, "default": ""}),
                "post_prompt": ("STRING", {"multiline": True, "default": ""}),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("modified_prompt",)
    FUNCTION = "modify_prompt"
    CATEGORY = "Custom Nodes/Prompt Tools"

    def modify_prompt(self, original_prompt, image_style="keep original", image_lighting="keep original", action="", action_details="", post_prompt=""):
        # Build the modified prompt in the specified order
        parts = []
        
        # Add image style
        if image_style != "keep original":
            parts.append(f"Image style: {image_style}.")
        
        # Add image lighting
        if image_lighting != "keep original":
            parts.append(f"Image lighting: {image_lighting}.")
        
        # Add action
        if action.strip():
            parts.append(action.strip())
        
        # Add action details
        if action_details.strip():
            parts.append(action_details.strip())
        
        # Add original prompt
        parts.append(original_prompt)
        
        # Add post prompt
        if post_prompt.strip():
            parts.append(post_prompt.strip())
        
        # Join all parts with spaces
        modified_prompt = " ".join(parts)
        
        return (modified_prompt,)