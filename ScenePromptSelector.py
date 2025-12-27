import re
import os
import torch
import numpy as np
from PIL import Image

class ScenePromptSelector:
    """
    A ComfyUI node that takes the prompts_text output from VideoSceneGenerationNode
    and allows selection of individual scene prompts with image output.
    Can also load keyframes directly from path if prompts_text is not provided.
    """
    
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "keyframes_path": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
                "scene_number": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 9999,
                    "step": 1
                }),
                "selected_prompt": ("STRING", {
                    "default": "",
                    "multiline": True
                })
            },
            "optional": {
                "prompts_text": ("STRING", {
                    "forceInput": True,
                    "multiline": True,
                    "default": ""
                })
            }
        }
    
    RETURN_TYPES = ("STRING", "IMAGE", "INT")
    RETURN_NAMES = ("selected_prompt", "scene_image", "total_scenes")
    FUNCTION = "select_scene_prompt"
    CATEGORY = "video/analysis"
    OUTPUT_NODE = True  # Enable UI output
    
    def parse_prompts(self, prompts_text):
        """Parse the prompts text and extract individual scene prompts"""
        if not prompts_text or not prompts_text.strip():
            return []
        
        # Split by double newlines to get individual scenes
        scenes = prompts_text.strip().split('\n\n')
        
        prompts = []
        for scene in scenes:
            scene = scene.strip()
            if not scene:
                continue
            
            # Try to extract prompt after "Scene X:"
            match = re.match(r'Scene\s+\d+:\s*(.+)', scene, re.DOTALL)
            if match:
                prompt = match.group(1).strip()
                prompts.append(prompt)
            else:
                # If pattern doesn't match, use the whole text
                prompts.append(scene)
        
        return prompts
    
    def get_keyframes_from_path(self, keyframes_path):
        """Get list of keyframe files from the directory"""
        if not keyframes_path:
            return []
        
        # Check if keyframes subdirectory exists
        keyframes_subdir = os.path.join(keyframes_path, "keyframes")
        if os.path.exists(keyframes_subdir):
            actual_path = keyframes_subdir
            print(f"Using keyframes subdirectory: {actual_path}")
        elif os.path.exists(keyframes_path):
            actual_path = keyframes_path
            print(f"Using direct path: {actual_path}")
        else:
            return []
        
        # Look for scene_XXX_YYmZZsWWWms.png files
        keyframes = []
        try:
            files = sorted(os.listdir(actual_path))
            for filename in files:
                if filename.startswith("scene_") and filename.endswith(".png"):
                    keyframes.append(os.path.join(actual_path, filename))
        except Exception as e:
            print(f"Error listing directory: {e}")
        
        return keyframes
    
    def load_prompt_from_file(self, keyframes_path, scene_idx):
        """Load prompt text from corresponding .txt file"""
        # Check if keyframes subdirectory exists
        keyframes_subdir = os.path.join(keyframes_path, "keyframes")
        if os.path.exists(keyframes_subdir):
            actual_path = keyframes_subdir
        else:
            actual_path = keyframes_path
        
        try:
            # Find the corresponding .txt file for the scene
            png_pattern = f"scene_{scene_idx + 1:03d}_"
            
            # Look for matching PNG file
            png_files = [f for f in os.listdir(actual_path) 
                        if f.startswith(png_pattern) and f.endswith('.png')]
            
            if not png_files:
                # Try without timestamp pattern
                png_files = [f for f in os.listdir(actual_path) 
                           if f == f"scene_{scene_idx + 1:03d}.png"]
            
            if png_files:
                # Get the PNG filename and create corresponding TXT filename
                png_file = png_files[0]
                txt_file = png_file.replace('.png', '.txt')
                prompt_path = os.path.join(actual_path, txt_file)
                
                if os.path.exists(prompt_path):
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        prompt_text = f.read().strip()
                    print(f"Loaded prompt from: {prompt_path}")
                    return prompt_text
                else:
                    print(f"Warning: Prompt file not found at {prompt_path}")
                    # Try to find any .txt file with scene number in name
                    txt_pattern = f"scene_{scene_idx + 1:03d}"
                    txt_files = [f for f in os.listdir(actual_path) 
                                if f.startswith(txt_pattern) and f.endswith('.txt')]
                    if txt_files:
                        prompt_path = os.path.join(actual_path, txt_files[0])
                        with open(prompt_path, 'r', encoding='utf-8') as f:
                            prompt_text = f.read().strip()
                        print(f"Loaded prompt from alternative: {prompt_path}")
                        return prompt_text
            return f"Scene {scene_idx + 1}"
        except Exception as e:
            print(f"Error loading prompt file: {e}")
            return f"Scene {scene_idx + 1}"
    
    def get_scene_image_path(self, keyframes_path, scene_idx):
        """Get the image path for a specific scene index"""
        # Check if keyframes subdirectory exists
        keyframes_subdir = os.path.join(keyframes_path, "keyframes")
        if os.path.exists(keyframes_subdir):
            actual_path = keyframes_subdir
        else:
            actual_path = keyframes_path
        
        try:
            # Look for pattern: scene_001_01m23s456ms.png
            pattern = f"scene_{scene_idx + 1:03d}_"
            png_files = [f for f in os.listdir(actual_path) 
                        if f.startswith(pattern) and f.endswith('.png')]
            
            if not png_files:
                # Fallback to old format: scene_001.png
                pattern = f"scene_{scene_idx + 1:03d}.png"
                png_files = [f for f in os.listdir(actual_path) 
                           if f == pattern]
            
            if png_files:
                # Sort to ensure we get the right one (should be only one anyway)
                png_files.sort()
                return os.path.join(actual_path, png_files[0])
            else:
                print(f"Warning: No image found for scene {scene_idx + 1}")
                return None
        except Exception as e:
            print(f"Error finding image: {e}")
            return None
    
    def load_image_as_tensor(self, image_path):
        """Load image and convert to ComfyUI tensor format"""
        try:
            if not image_path or not os.path.exists(image_path):
                # Return a blank image if loading fails
                blank = np.zeros((512, 512, 3), dtype=np.float32)
                return torch.from_numpy(blank)[None,]
            
            img = Image.open(image_path)
            img = img.convert("RGB")
            img_np = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np)[None,]
            return img_tensor
        except Exception as e:
            print(f"Error loading image: {e}")
            # Return a blank image if loading fails
            blank = np.zeros((512, 512, 3), dtype=np.float32)
            return torch.from_numpy(blank)[None,]
    
    def select_scene_prompt(self, keyframes_path, scene_number, prompts_text=None, selected_prompt=""):
        """Select a specific scene prompt by number"""
        print(f"=== ScenePromptSelector.select_scene_prompt called ===")
        print(f"keyframes_path: {keyframes_path}")
        print(f"scene_number: {scene_number}")
        print(f"prompts_text provided: {prompts_text is not None and prompts_text != ''}")
        print(f"selected_prompt (from widget): {selected_prompt[:100] if selected_prompt else 'empty'}")
        
        # If we have a selected_prompt from the widget (edited in UI), use that
        if selected_prompt and selected_prompt.strip():
            print("Using selected_prompt from widget (UI-edited)")
            # Still need to load the image
            if keyframes_path:
                scene_idx = max(0, scene_number - 1)
                image_path = self.get_scene_image_path(keyframes_path, scene_idx)
                if image_path:
                    scene_image = self.load_image_as_tensor(image_path)
                else:
                    scene_image = self.load_image_as_tensor("")
            else:
                scene_image = self.load_image_as_tensor("")
            
            return {
                "ui": {"text": [selected_prompt]},
                "result": (selected_prompt, scene_image, 1)
            }
        
        try:
            # Determine if we're using prompts or keyframes
            if prompts_text:
                # Parse all prompts
                prompts = self.parse_prompts(prompts_text)
                
                if not prompts:
                    blank_image = self.load_image_as_tensor("")
                    return {
                        "ui": {"text": ["No prompts found"]},
                        "result": ("No prompts found", blank_image, 0)
                    }
                
                total_scenes = len(prompts)
                
                # Clamp scene_number to valid range
                scene_idx = max(0, min(scene_number - 1, total_scenes - 1))
                
                # Get selected prompt
                selected_prompt = prompts[scene_idx]
                
                # Get image path for selected scene
                if keyframes_path:
                    image_path = self.get_scene_image_path(keyframes_path, scene_idx)
                    if image_path:
                        scene_image = self.load_image_as_tensor(image_path)
                        print(f"Loaded image: {image_path}")
                    else:
                        print(f"Warning: Image not found for scene {scene_idx + 1}")
                        scene_image = self.load_image_as_tensor("")
                else:
                    scene_image = self.load_image_as_tensor("")
                
                print(f"Selected Scene {scene_idx + 1}/{total_scenes}")
                print(f"Prompt: {selected_prompt}")
                
                # Return with UI data for preview
                return {
                    "ui": {"text": [selected_prompt]},
                    "result": (selected_prompt, scene_image, total_scenes)
                }
            
            else:
                # Load directly from keyframes path
                keyframes = self.get_keyframes_from_path(keyframes_path)
                
                if not keyframes:
                    blank_image = self.load_image_as_tensor("")
                    return {
                        "ui": {"text": ["No keyframes found"]},
                        "result": ("No keyframes found", blank_image, 0)
                    }
                
                total_scenes = len(keyframes)
                
                # Clamp scene_number to valid range
                scene_idx = max(0, min(scene_number - 1, total_scenes - 1))
                
                # Load the selected keyframe
                selected_keyframe = keyframes[scene_idx]
                scene_image = self.load_image_as_tensor(selected_keyframe)
                
                # Load prompt from corresponding .txt file
                selected_prompt = self.load_prompt_from_file(keyframes_path, scene_idx)
                
                print(f"Selected Scene {scene_idx + 1}/{total_scenes}")
                print(f"Keyframe: {selected_keyframe}")
                print(f"Prompt: {selected_prompt}")
                
                # Return with UI data for preview
                return {
                    "ui": {"text": [selected_prompt]},
                    "result": (selected_prompt, scene_image, total_scenes)
                }
            
        except Exception as e:
            error_msg = f"Error selecting prompt: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            blank_image = self.load_image_as_tensor("")
            return {
                "ui": {"text": [error_msg]},
                "result": (error_msg, blank_image, 0)
            }


# Node registration
NODE_CLASS_MAPPINGS = {
    "ScenePromptSelector": ScenePromptSelector
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ScenePromptSelector": "Scene Prompt Selector"
}