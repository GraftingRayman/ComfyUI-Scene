import os
import torch
import numpy as np
from PIL import Image
import cv2
import folder_paths
import json
import hashlib
from typing import List
import warnings
warnings.filterwarnings("ignore")

# Import comfy.utils for progress bar
try:
    import comfy.utils
    USE_COMFY_PROGRESS = True
except ImportError:
    USE_COMFY_PROGRESS = False
    print("Note: comfy.utils not available, using simple progress display")

class VideoSceneGenerationNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_file": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "output_dir": ("STRING", {
                    "default": "scene_outputs",
                    "multiline": False,
                }),
                "start_time": ("FLOAT", {
                    "default": 9.0,
                }),
                "end_time": ("FLOAT", {
                    "default": 10.0,
                }),
                "scene_threshold": ("FLOAT", {
                    "default": 27.0,
                }),
                "max_description_length": ("INT", {
                    "default": 512,
                }),
                "save_scenes": ("BOOLEAN", {
                    "default": True,
                }),
                "generate_descriptions": ("BOOLEAN", {
                    "default": True,
                }),
                "use_cache": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Use Cache",
                    "label_off": "Force Regenerate"
                }),
                # New: Scene detection method dropdown
                "scene_detection_method": ([
                    "opencv",
                    "pyscene_openvideo", 
                    "pyscene_videomanager"
                ], {
                    "default": "opencv"
                }),
                # UI control inputs
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

    RETURN_TYPES = ("STRING", "LIST", "STRING", "STRING")
    RETURN_NAMES = ("output_path", "scene_paths", "metadata_json", "selected_description")
    FUNCTION = "extract_scenes"
    CATEGORY = "Video Processing"
    OUTPUT_NODE = True

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.progress_bar = None
        
    def create_progress_bar(self, total, desc=""):
        """Create a progress bar"""
        if USE_COMFY_PROGRESS:
            self.progress_bar = comfy.utils.ProgressBar(total)
            print(f"{desc} (0/{total})")
        else:
            self.progress_bar = None
            print(f"{desc}: Starting...")
        
    def update_progress(self, current, total, desc=""):
        """Update progress bar"""
        if USE_COMFY_PROGRESS and self.progress_bar:
            self.progress_bar.update(1)
            if current == total:
                print(f"{desc}: Complete! ({current}/{total})")
        else:
            percent = (current / total) * 100 if total > 0 else 0
            print(f"{desc}: {current}/{total} ({percent:.1f}%)")
        
    def get_cache_key(self, video_file, start_time, end_time, scene_threshold, 
                     max_description_length, save_scenes, generate_descriptions, 
                     output_dir, scene_detection_method):
        """Generate a unique cache key based on input parameters"""
        params_str = f"{video_file}_{start_time}_{end_time}_{scene_threshold}_{max_description_length}_{save_scenes}_{generate_descriptions}_{output_dir}_{scene_detection_method}"
        return hashlib.md5(params_str.encode()).hexdigest()[:16]
    
    def load_cached_results(self, cache_key, scene_output_dir):
        """Load cached results if they exist"""
        cache_file = os.path.join(scene_output_dir, f"cache_{cache_key}.json")
        
        if not os.path.exists(cache_file):
            print(f"Cache file not found: {cache_file}")
            return None
            
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            print(f"Found cache file: {cache_file}")
            
            scene_paths = cache_data.get("scene_paths", [])
            
            if not scene_paths:
                print("Cache has no scene paths")
                return None
                
            print(f"Cache has {len(scene_paths)} scenes")
            
            # Check if the first scene file exists
            first_scene = scene_paths[0] if scene_paths else None
            if first_scene and not os.path.exists(first_scene):
                print(f"First scene file missing: {first_scene}")
                print("Cache invalid, regenerating...")
                return None
            
            print("Cache validation passed!")
            return cache_data
            
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None
    
    def save_cached_results(self, cache_key, scene_output_dir, results):
        """Save results to cache"""
        cache_file = os.path.join(scene_output_dir, f"cache_{cache_key}.json")
        
        try:
            cache_data = {
                "scene_paths": results.get("scene_paths", []),
                "scene_timestamps": results.get("scene_timestamps", []),
                "metadata": results.get("metadata", {}),
                "cache_key": cache_key,
                "video_file": results.get("video_file", ""),
                "output_dir": results.get("output_dir", ""),
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            print(f"Results cached to: {cache_file}")
            print(f"Cache key: {cache_key}")
            
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def load_moondream_model(self):
        """Load Moondream2 model exactly as in your working code"""
        try:
            print(f"\nLoading Moondream2 model: vikhyatk/moondream2\n")
            
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            tokenizer = AutoTokenizer.from_pretrained(
                "vikhyatk/moondream2", 
                trust_remote_code=True
            )
            
            model = AutoModelForCausalLM.from_pretrained(
                "vikhyatk/moondream2",
                trust_remote_code=True,
                dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            ).to(self.device)
            
            model.eval()
            print("Model loaded successfully!\n")
            return tokenizer, model
            
        except Exception as e:
            print(f"Failed to load model: {e}")
            return None, None

    def generate_caption(self, image_path, tokenizer, model):
        """Generate caption using Moondream2 exactly as in your working code"""
        try:
            image = Image.open(image_path).convert("RGB")
            enc_image = model.encode_image(image)
            
            question = "Describe this image in detail."
            with torch.no_grad():
                answer = model.answer_question(enc_image, question, tokenizer)
            
            caption = answer.strip()
            
            # Clean up as in your working code
            patterns_to_remove = [
                question,
                f"{question}:",
                f"Question: {question}",
                f"Q: {question}",
            ]
            
            for pattern in patterns_to_remove:
                if caption.lower().startswith(pattern.lower()):
                    caption = caption[len(pattern):].lstrip(" :-")
                    break
            
            if caption.lower().startswith("answer:"):
                caption = caption[7:].strip()
            elif caption.lower().startswith("a:"):
                caption = caption[2:].strip()
            
            return caption.strip()
            
        except Exception as e:
            print(f"Error generating caption: {e}")
            return f"Caption generation failed: {str(e)}"

    def save_description_txt(self, image_path, description):
        """Save description as .txt file with same name as image"""
        txt_path = os.path.splitext(image_path)[0] + '.txt'
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(description + '\n')
        return txt_path

    def extract_scenes(self, video_file, output_dir, start_time, end_time, scene_threshold, 
                      max_description_length, save_scenes, generate_descriptions,
                      use_cache, scene_detection_method, selected_scene_index, scene_description):
        
        # Get ComfyUI output directory
        comfy_output_dir = folder_paths.get_output_directory()
        
        # Use custom output directory name
        if not output_dir:
            output_dir = "scene_outputs"
        
        # Sanitize the output directory name
        output_dir = self.sanitize_filename(output_dir)
        
        scene_output_dir = os.path.join(comfy_output_dir, output_dir)
        os.makedirs(scene_output_dir, exist_ok=True)
        
        # Validate video file
        if not os.path.exists(video_file):
            print(f"Error: Video file not found: {video_file}")
            return self.return_empty(scene_output_dir)
        
        # Check cache first
        cache_key = self.get_cache_key(video_file, start_time, end_time, scene_threshold,
                                      max_description_length, save_scenes, generate_descriptions, 
                                      output_dir, scene_detection_method)
        
        print(f"Cache key: {cache_key}")
        print(f"Use cache: {use_cache}")
        print(f"Scene detection method: {scene_detection_method}")
        
        cached_results = None
        if use_cache:
            cached_results = self.load_cached_results(cache_key, scene_output_dir)
        
        if cached_results:
            # Use cached results
            scene_paths = cached_results["scene_paths"]
            scene_timestamps = cached_results.get("scene_timestamps", [])
            metadata = cached_results.get("metadata", {})
            
            print(f"✓ Loaded {len(scene_paths)} scenes from cache")
            
            # Update metadata path if needed
            metadata["full_output_path"] = scene_output_dir
            metadata["output_directory_name"] = output_dir
            
        else:
            print("No cache found or cache invalid, generating scenes...")
            
            # Convert minutes to seconds
            start_seconds = start_time * 60
            end_seconds = end_time * 60
            
            print(f"Detecting scenes from {start_seconds}s to {end_seconds}s...")
            print(f"Output directory: {scene_output_dir}")
            
            # Extract scenes based on selected method
            if scene_detection_method == "opencv":
                print("Using OpenCV scene detection")
                scene_timestamps = self.detect_scenes_opencv(video_file, start_seconds, end_seconds, scene_threshold)
            elif scene_detection_method == "pyscene_openvideo":
                print("Using PySceneDetect OpenVideo scene detection")
                scene_timestamps = self.detect_scenes_pyscene_openvideo(video_file, start_seconds, end_seconds, scene_threshold)
            elif scene_detection_method == "pyscene_videomanager":
                print("Using PySceneDetect VideoManager scene detection")
                scene_timestamps = self.detect_scenes_pyscene_videomanager(video_file, start_seconds, end_seconds, scene_threshold)
            else:
                print(f"Unknown scene detection method: {scene_detection_method}, defaulting to OpenCV")
                scene_timestamps = self.detect_scenes_opencv(video_file, start_seconds, end_seconds, scene_threshold)
            
            print(f"Found {len(scene_timestamps)} scenes")
            
            # Extract and save scene frames with progress bar
            scene_paths = []
            if save_scenes:
                print(f"Extracting {len(scene_timestamps)} scene frames...")
                
                # Create progress bar for scene extraction
                total_scenes = len(scene_timestamps)
                self.create_progress_bar(total_scenes, "Extracting scenes")
                
                for i, timestamp in enumerate(scene_timestamps):
                    scene_filename = f"scene_{i:04d}_at_{timestamp:.2f}s.png"
                    scene_path = os.path.join(scene_output_dir, scene_filename)
                    
                    # Update progress
                    self.update_progress(i + 1, total_scenes, f"Extracting scene {i+1}/{total_scenes}")
                    
                    self.extract_frame(video_file, timestamp, scene_path)
                    scene_paths.append(scene_path)
                
            else:
                # Just create paths without extracting
                for i, timestamp in enumerate(scene_timestamps):
                    scene_filename = f"scene_{i:04d}_at_{timestamp:.2f}s.png"
                    scene_path = os.path.join(scene_output_dir, scene_filename)
                    scene_paths.append(scene_path)
            
            # Generate descriptions AFTER all scenes are extracted
            if generate_descriptions and save_scenes and scene_paths:
                print("\nLoading Moondream2 model for caption generation...")
                tokenizer, model = self.load_moondream_model()
                if tokenizer and model:
                    total_scenes = len(scene_paths)
                    print(f"Generating captions for {total_scenes} scenes...")
                    
                    # Create progress bar for caption generation
                    self.create_progress_bar(total_scenes, "Generating captions")
                    
                    for i, scene_path in enumerate(scene_paths):
                        if os.path.exists(scene_path):
                            # Update progress
                            self.update_progress(i + 1, total_scenes, f"Generating caption {i+1}/{total_scenes}")
                            
                            caption = self.generate_caption(scene_path, tokenizer, model)
                            # Truncate if needed
                            if len(caption) > max_description_length:
                                caption = caption[:max_description_length].rsplit(' ', 1)[0] + "..."
                            
                            # Save as .txt file with same name
                            self.save_description_txt(scene_path, caption)
                            print(f"Saved description to: {os.path.basename(scene_path).replace('.png', '.txt')}")
                    
                    # Clear model from memory
                    del model
                    del tokenizer
                    torch.cuda.empty_cache()
                    print("Moondream2 model unloaded from memory")
            
            # Create metadata
            metadata = {
                "video_file": video_file,
                "output_directory_name": output_dir,
                "full_output_path": scene_output_dir,
                "start_time": start_time,
                "end_time": end_time,
                "scene_threshold": scene_threshold,
                "max_description_length": max_description_length,
                "generate_descriptions": generate_descriptions,
                "scene_detection_method": scene_detection_method,
                "total_scenes": len(scene_timestamps),
                "scenes": []
            }
            
            for i, (timestamp, img_path) in enumerate(zip(scene_timestamps, scene_paths)):
                txt_path = img_path.replace('.png', '.txt')
                description = ""
                if os.path.exists(txt_path):
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        description = f.read().strip()
                
                metadata["scenes"].append({
                    "index": i,
                    "timestamp": timestamp,
                    "image_file": os.path.basename(img_path),
                    "description_file": os.path.basename(txt_path),
                    "description": description,
                    "image_path": img_path,
                    "description_path": txt_path
                })
            
            # Save metadata
            metadata_path = os.path.join(scene_output_dir, "metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Cache the results
            if use_cache:
                self.save_cached_results(cache_key, scene_output_dir, {
                    "scene_paths": scene_paths,
                    "scene_timestamps": scene_timestamps,
                    "metadata": metadata,
                    "video_file": video_file,
                    "output_dir": output_dir,
                })
        
        # Adjust selected_scene_index from 1-based to 0-based for internal use
        internal_index = selected_scene_index - 1
        
        # Get selected description from .txt file or UI input
        selected_description = ""
        if 0 <= internal_index < len(scene_paths):
            scene_path = scene_paths[internal_index]
            txt_path = scene_path.replace('.png', '.txt')
            
            # If scene_description is provided from UI, use it (edited version)
            if scene_description and scene_description.strip():
                selected_description = scene_description
                # Save the edited description to .txt file
                self.save_description_txt(scene_path, scene_description)
                print(f"Saved edited description for scene {selected_scene_index}")
            elif os.path.exists(txt_path):
                # Load description from .txt file
                with open(txt_path, 'r', encoding='utf-8') as f:
                    selected_description = f.read().strip()
        else:
            # If index is out of bounds, use first scene
            if scene_paths:
                internal_index = 0
                scene_path = scene_paths[0]
                txt_path = scene_path.replace('.png', '.txt')
                if os.path.exists(txt_path):
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        selected_description = f.read().strip()
        
        print(f"\n✓ Complete! Output saved to: {scene_output_dir}")
        print(f"  - Custom directory name: {output_dir}")
        print(f"  - Images: {len(scene_paths)}")
        print(f"  - Selected scene: {selected_scene_index} (internal: {internal_index})")
        print(f"  - Selected description length: {len(selected_description)}")
        print(f"  - Cache used: {cached_results is not None}")
        print(f"  - Scene detection method: {scene_detection_method}")
        
        # Return with UI data - ALL VALUES MUST BE LISTS
        return {
            "ui": {
                "text": [selected_description],  # For display
                "scene_paths": [scene_paths],  # List containing list
                "total_scenes": [len(scene_paths)],  # List containing int
                "selected_index": [selected_scene_index],  # List containing int
            },
            "result": (scene_output_dir, scene_paths, json.dumps(metadata, indent=2), selected_description)
        }
    
    def return_empty(self, scene_output_dir):
        """Return empty results when video file not found"""
        return {
            "ui": {
                "text": [""],  # Empty string in list
                "scene_paths": [[]],  # Empty list in list
                "total_scenes": [0],  # Zero in list
                "selected_index": [1],  # 1 in list
            },
            "result": (scene_output_dir, [], "{}", "")
        }

    def sanitize_filename(self, filename):
        """Sanitize filename to be safe for all filesystems"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        filename = filename.strip('. ')
        if len(filename) > 255:
            filename = filename[:255]
        if not filename:
            filename = "scene_outputs"
        return filename

    def detect_scenes_opencv(self, video_path, start_seconds, end_seconds, threshold):
        """Simple scene detection using OpenCV"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return []
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30.0
            
            start_frame = int(start_seconds * fps)
            end_frame = int(end_seconds * fps)
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            end_frame = min(end_frame, total_frames - 1)
            
            if start_frame >= end_frame:
                return [start_seconds]
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            scene_timestamps = [start_seconds]
            prev_frame = None
            
            while cap.isOpened():
                ret, frame = cap.read()
                current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                
                if not ret or current_frame > end_frame:
                    break
                
                if (current_frame - start_frame) % 5 != 0:
                    continue
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)
                
                if prev_frame is not None:
                    frame_diff = cv2.absdiff(prev_frame, gray)
                    _, thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)
                    diff_percentage = np.sum(thresh) / (thresh.size * 255)
                    
                    threshold_scaled = threshold / 1000
                    if diff_percentage > threshold_scaled:
                        current_time = current_frame / fps
                        if (current_time - scene_timestamps[-1]) > 2.0:
                            scene_timestamps.append(current_time)
                
                prev_frame = gray
            
            cap.release()
            
            if scene_timestamps and (end_seconds - scene_timestamps[-1]) > 3.0:
                scene_timestamps.append(min(end_seconds, total_frames / fps))
            
            return scene_timestamps
            
        except Exception as e:
            print(f"OpenCV scene detection error: {e}")
            return [start_seconds]

    def detect_scenes_pyscene_openvideo(self, video_path, start_seconds, end_seconds, threshold):
        """Scene detection using PySceneDetect open_video method"""
        try:
            # Import scenedetect here to avoid dependency issues
            from scenedetect import open_video, SceneManager
            from scenedetect.detectors import ContentDetector
            from scenedetect.frame_timecode import FrameTimecode
            
            print("Opening video with PySceneDetect open_video...")
            video_stream = open_video(video_path)
            fps = video_stream.frame_rate
            
            print(f"Video FPS: {fps}")
            
            # Create scene manager and add detector
            sm = SceneManager()
            sm.add_detector(ContentDetector(threshold=threshold))
            
            # Detect scenes
            sm.detect_scenes(video=video_stream)
            all_scenes = sm.get_scene_list()
            
            # Filter scenes by time range
            scenes = []
            for scene in all_scenes:
                scene_start = scene[0].get_seconds()
                scene_end = scene[1].get_seconds()
                
                include_scene = True
                if start_seconds is not None and scene_end < start_seconds:
                    include_scene = False
                if end_seconds is not None and scene_start > end_seconds:
                    include_scene = False
                
                if include_scene:
                    scenes.append(scene)
            
            # Extract scene start timestamps
            scene_timestamps = []
            for scene in scenes:
                scene_start = scene[0].get_seconds()
                # Only include scenes within our time range
                if (start_seconds is None or scene_start >= start_seconds) and \
                   (end_seconds is None or scene_start <= end_seconds):
                    scene_timestamps.append(scene_start)
            
            # If no scenes found within range, add the start time
            if not scene_timestamps:
                scene_timestamps.append(start_seconds)
            
            print(f"PySceneDetect OpenVideo found {len(scene_timestamps)} scenes")
            return scene_timestamps
            
        except ImportError:
            print("PySceneDetect not installed. Please install with: pip install scenedetect")
            return [start_seconds]
        except Exception as e:
            print(f"PySceneDetect OpenVideo scene detection error: {e}")
            return [start_seconds]

    def detect_scenes_pyscene_videomanager(self, video_path, start_seconds, end_seconds, threshold):
        """Scene detection using PySceneDetect VideoManager method"""
        try:
            # Import scenedetect here to avoid dependency issues
            from scenedetect import VideoManager, SceneManager
            from scenedetect.detectors import ContentDetector
            from scenedetect.frame_timecode import FrameTimecode
            
            print("Opening video with PySceneDetect VideoManager...")
            vm = VideoManager([video_path])
            
            vm.start()
            fps = vm.get_framerate()
            vm.release()
            
            # Recreate video manager with time range settings
            vm = VideoManager([video_path])
            
            # Set time range if specified
            if start_seconds is not None and start_seconds > 0:
                start_time = FrameTimecode(timecode=start_seconds, fps=fps)
                print(f"Setting start time to: {start_seconds}s ({start_time.get_frames()} frames)")
                
            if end_seconds is not None and end_seconds > 0:
                end_time = FrameTimecode(timecode=end_seconds, fps=fps)
                print(f"Setting end time to: {end_seconds}s ({end_time.get_frames()} frames)")
            
            # Apply time range to video manager
            if start_seconds is not None and start_seconds > 0:
                if end_seconds is not None and end_seconds > 0:
                    vm.set_duration(start_time=start_time, end_time=end_time)
                else:
                    vm.set_duration(start_time=start_time)
            elif end_seconds is not None and end_seconds > 0:
                vm.set_duration(end_time=end_time)
            
            # Create scene manager and add detector
            sm = SceneManager()
            sm.add_detector(ContentDetector(threshold=threshold))
            
            # Detect scenes
            vm.start()
            sm.detect_scenes(frame_source=vm)
            scenes = sm.get_scene_list()
            vm.release()
            
            # Extract scene start timestamps
            scene_timestamps = []
            for scene in scenes:
                scene_start = scene[0].get_seconds()
                scene_timestamps.append(scene_start)
            
            # If no scenes found, add the start time
            if not scene_timestamps:
                scene_timestamps.append(start_seconds)
            
            print(f"PySceneDetect VideoManager found {len(scene_timestamps)} scenes")
            return scene_timestamps
            
        except ImportError:
            print("PySceneDetect not installed. Please install with: pip install scenedetect")
            return [start_seconds]
        except Exception as e:
            print(f"PySceneDetect VideoManager scene detection error: {e}")
            return [start_seconds]

    def extract_frame(self, video_path, timestamp, output_path):
        """Extract a frame at timestamp"""
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30
            
            frame_number = int(timestamp * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            
            ret, frame = cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                Image.fromarray(frame_rgb).save(output_path, 'PNG')
                print(f"  Saved: {os.path.basename(output_path)}")
            else:
                print(f"  Warning: Could not extract frame at {timestamp}s")
            
            cap.release()
        except Exception as e:
            print(f"Error extracting frame: {e}")

# Register the node
NODE_CLASS_MAPPINGS = {
    "VideoSceneGenerationNode": VideoSceneGenerationNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneGenerationNode": "Video Scene Analysis & Prompt Generation",
}
