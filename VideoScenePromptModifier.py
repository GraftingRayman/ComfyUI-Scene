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
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("modified_prompt",)
    FUNCTION = "modify_prompt"
    CATEGORY = "Custom Nodes/Prompt Tools"

    def modify_prompt(self, original_prompt, image_style="keep original", image_lighting="keep original"):
        modified_prompt = original_prompt
        
        # Function to replace a specific pattern
        def replace_section(pattern, new_value, prompt_text):
            if new_value != "keep original":
                return re.sub(
                    pattern,
                    f'Image {new_value[0]}: {new_value[1]}.',
                    prompt_text,
                    count=1
                )
            return prompt_text
        
        # Replace image style if needed
        if image_style != "keep original":
            modified_prompt = replace_section(
                r'Image style:\s*[^.]+\.',
                ("style", image_style),
                modified_prompt
            )
        
        # Replace image lighting if needed
        if image_lighting != "keep original":
            modified_prompt = replace_section(
                r'Image lighting:\s*[^.]+\.',
                ("lighting", image_lighting),
                modified_prompt
            )
        
        # If the pattern doesn't exist, add it
        if image_style != "keep original" and "Image style:" not in modified_prompt:
            modified_prompt = f"Image style: {image_style}. {modified_prompt}"
        
        if image_lighting != "keep original" and "Image lighting:" not in modified_prompt:
            modified_prompt = f"Image lighting: {image_lighting}. {modified_prompt}"
        
        return (modified_prompt,)