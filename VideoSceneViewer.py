import os
import json
from PIL import Image
import warnings
warnings.filterwarnings("ignore")

try:
    import torch
    import numpy as np
    IMPORT_SUCCESS = True
except ImportError:
    IMPORT_SUCCESS = False
    print("Warning: torch/numpy not available")

class VideoSceneViewer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "scene_directory": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "selected_scene_index": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 9999,
                }),
                "scene_description": ("STRING", {
                    "default": "",
                    "multiline": True,
                }),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("scene_image", "scene_description")
    FUNCTION = "view_scene"
    CATEGORY = "Video Processing"
    OUTPUT_NODE = True

    def __init__(self):
        if IMPORT_SUCCESS:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = None
        # Track last processed values to detect changes
        self.last_directory = None
        self.last_index = None
    
    def find_image_txt_pairs(self, scene_directory):
        """Find all image files that have an exact matching .txt file"""
        image_files = []
        
        if not os.path.exists(scene_directory):
            print(f"Error: Directory not found: {scene_directory}")
            return []
        
        try:
            # Get all files in directory
            all_files = os.listdir(scene_directory)
            
            # First, create a set of all .txt files (without extension)
            txt_basenames = set()
            for file in all_files:
                if file.lower().endswith('.txt'):
                    basename = os.path.splitext(file)[0]
                    txt_basenames.add(basename)
            
            print(f"Found {len(txt_basenames)} .txt files")
            
            # Supported image extensions
            image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff'}
            
            # Now find image files that have matching .txt files
            for file in all_files:
                file_path = os.path.join(scene_directory, file)
                if not os.path.isfile(file_path):
                    continue
                
                # Check file extension
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in image_extensions:
                    basename = os.path.splitext(file)[0]
                    
                    # Check if there's an exact matching .txt file
                    if basename in txt_basenames:
                        image_files.append({
                            "path": file_path,
                            "filename": file,
                            "basename": basename
                        })
            
            # Natural sort for better ordering
            def natural_sort_key(item):
                import re
                filename = item["filename"]
                return [int(text) if text.isdigit() else text.lower()
                       for text in re.split(r'(\d+)', filename)]
            
            image_files.sort(key=natural_sort_key)
            
            print(f"Found {len(image_files)} image files with matching .txt descriptions")
            
            return image_files
            
        except Exception as e:
            print(f"Error finding image/txt pairs: {e}")
            return []
    
    def load_image_as_tensor(self, image_path):
        """Load image and convert to ComfyUI compatible tensor"""
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")
            
            # Convert to numpy array
            image_array = np.array(image).astype(np.float32) / 255.0
            
            # Convert to tensor (ComfyUI format: [1, H, W, C])
            image_tensor = torch.from_numpy(image_array).unsqueeze(0)
            
            return image_tensor
            
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            # Return blank image tensor
            return torch.zeros((1, 512, 512, 3), dtype=torch.float32)
    
    def get_description_from_txt(self, txt_path):
        """Get description from the txt file path"""
        try:
            # Read the .txt file
            if os.path.exists(txt_path):
                with open(txt_path, 'r', encoding='utf-8') as f:
                    description = f.read().strip()
                print(f"Loaded description from {txt_path}, length: {len(description)}")
                return description
            else:
                print(f"Description file not found: {txt_path}")
                return ""
                
        except Exception as e:
            print(f"Error reading description file: {e}")
            return ""
    
    def view_scene(self, scene_directory, selected_scene_index, scene_description):
        """View scene from directory and return image and description"""
        
        print(f"\n=== Video Scene Viewer ===")
        print(f"Input directory: {scene_directory}")
        print(f"Selected index: {selected_scene_index}")
        print(f"Scene description widget value: '{scene_description[:100] if scene_description else 'empty'}...'")
        
        # Validate directory
        if not scene_directory or not os.path.exists(scene_directory):
            print(f"Error: Directory not found or not specified: {scene_directory}")
            return self.return_empty()
        
        # Find image files that have matching .txt files
        scene_files_info = self.find_image_txt_pairs(scene_directory)
        
        if not scene_files_info:
            print(f"No image files with matching .txt descriptions found in {scene_directory}")
            return self.return_empty()
        
        total_scenes = len(scene_files_info)
        
        # Adjust selected_scene_index from 1-based to 0-based
        internal_index = selected_scene_index - 1
        
        # Ensure index is within bounds
        if internal_index < 0:
            internal_index = 0
            selected_scene_index = 1
        elif internal_index >= total_scenes:
            internal_index = total_scenes - 1
            selected_scene_index = total_scenes
        
        # Get selected scene info
        selected_scene_info = scene_files_info[internal_index]
        scene_path = selected_scene_info["path"]
        txt_path = os.path.join(os.path.dirname(scene_path), f"{selected_scene_info['basename']}.txt")
        
        print(f"Total scenes with descriptions: {total_scenes}")
        print(f"Selected scene: {selected_scene_index}")
        print(f"Image file: {selected_scene_info['filename']}")
        print(f"Description file: {txt_path}")
        
        # Determine if this is a new scene selection or if user is saving
        directory_changed = scene_directory != self.last_directory
        index_changed = selected_scene_index != self.last_index
        
        # Update tracking
        self.last_directory = scene_directory
        self.last_index = selected_scene_index
        
        # Get description
        final_description = ""
        
        # If scene_description is provided from UI AND it's not a new scene selection, save it
        if scene_description and scene_description.strip() and not (directory_changed or index_changed):
            # This is an edit being saved
            final_description = scene_description
            print("User edited description, saving to file...")
            
            try:
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(scene_description)
                print(f"✓ Saved edited description to: {txt_path}")
            except Exception as e:
                print(f"Error saving description: {e}")
        else:
            # Load fresh description from file (new scene or first load)
            final_description = self.get_description_from_txt(txt_path)
            print(f"Loaded fresh description from file")
        
        # Load image as tensor
        print(f"Loading image: {selected_scene_info['filename']}")
        image_tensor = self.load_image_as_tensor(scene_path)
        
        # Prepare data for UI
        scene_filenames = [info["filename"] for info in scene_files_info]
        scene_paths = [info["path"] for info in scene_files_info]
        scene_basenames = [info["basename"] for info in scene_files_info]
        
        # Calculate txt file paths
        txt_paths = []
        for info in scene_files_info:
            txt_file_path = os.path.join(os.path.dirname(info["path"]), f"{info['basename']}.txt")
            txt_paths.append(txt_file_path)
        
        print(f"\n✓ Scene loaded successfully")
        print(f"  - Total scenes: {total_scenes}")
        print(f"  - Selected scene: {selected_scene_index}")
        print(f"  - Description length: {len(final_description)}")
        print(f"  - Image shape: {image_tensor.shape}")
        print(f"  - Using secured API routes for file access")
        
        # Return UI data for frontend
        return {
            "ui": {
                "text": [final_description],
                "scene_filenames": [scene_filenames],
                "scene_paths": [scene_paths],  # Full paths for new API
                "scene_basenames": [scene_basenames],
                "txt_paths": [txt_paths],  # Full paths to txt files
                "total_scenes": [total_scenes],
                "selected_index": [selected_scene_index],
                "directory": [scene_directory],
            },
            "result": (image_tensor, final_description)
        }
    
    def return_empty(self):
        """Return empty results when no scenes found"""
        if IMPORT_SUCCESS:
            blank_tensor = torch.zeros((1, 512, 512, 3), dtype=torch.float32)
        else:
            blank_tensor = None
        
        return {
            "ui": {
                "text": [""],
                "scene_filenames": [[]],
                "scene_paths": [[]],
                "scene_basenames": [[]],
                "txt_paths": [[]],
                "total_scenes": [0],
                "selected_index": [1],
                "directory": [""],
            },
            "result": (blank_tensor, "")
        }

# Register the node
NODE_CLASS_MAPPINGS = {
    "VideoSceneViewer": VideoSceneViewer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneViewer": "Video Scene Viewer",
}