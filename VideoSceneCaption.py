# VideoSceneCaption.py - Scene video captioning with selected_scene_index
import os
import torch
import cv2
import numpy as np
from PIL import Image
import folder_paths
import json
import hashlib
import urllib.parse
from typing import List
import warnings
warnings.filterwarnings("ignore")

try:
    import comfy.utils
    USE_COMFY_PROGRESS = True
except ImportError:
    USE_COMFY_PROGRESS = False
    print("Note: comfy.utils not available, using simple progress display")

class VideoSceneCaption:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "scene_video_paths": ("LIST", {
                    "default": [],
                }),
                "llm_model": ([
                    "phi-3-mini-4k",
                    "qwen2.5-7b", 
                    "mistral-7b",
                    "none"
                ], {
                    "default": "phi-3-mini-4k"
                }),
                "sampling_interval": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.5,
                    "max": 3.0,
                    "step": 0.1,
                    "display": "slider"
                }),
                "max_frames": ("INT", {
                    "default": 6,
                    "min": 3,
                    "max": 12,
                    "step": 1,
                    "display": "slider"
                }),
                "max_description_length": ("INT", {
                    "default": 500,
                    "min": 200,
                    "max": 1000,
                    "step": 50,
                }),
                "use_cache": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Use Cache",
                    "label_off": "Force Regenerate"
                }),
                "selected_scene_index": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 9999,
                }),
            },
            "optional": {
                "video_scenes_output_path": ("STRING", {
                    "default": "",
                }),
            }
        }

    RETURN_TYPES = ("STRING", "LIST", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("output_path", "scene_captions", "metadata_json", "selected_caption", "debug_info")
    FUNCTION = "generate_captions"
    CATEGORY = "Video Processing"
    OUTPUT_NODE = True

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.progress_bar = None
        self.moondream_tokenizer = None
        self.moondream_model = None
        self.llm_tokenizer = None
        self.llm_model = None
        self.last_video_paths = None
        self.last_index = None
    
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
    
    def get_video_duration(self, video_path):
        """Get video duration in seconds"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return 0
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if fps > 0:
                duration = frame_count / fps
            else:
                duration = 0
            
            cap.release()
            return duration
        except Exception as e:
            print(f"Error getting video duration: {e}")
            return 0
    
    def extract_keyframes(self, video_path, interval_seconds, max_frames):
        """Extract keyframes at regular intervals throughout the video"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return []
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            
            # Always extract at least 3 frames (start, middle, end)
            num_frames = min(int(duration / interval_seconds) + 1, max_frames)
            if num_frames < 3:
                num_frames = 3
            
            frames = []
            for i in range(num_frames):
                # Evenly distribute frames throughout the video
                time_point = (i / (num_frames - 1)) * duration if num_frames > 1 else 0
                frame_idx = int(time_point * fps)
                frame_idx = min(frame_idx, total_frames - 1)
                
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if ret:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append((time_point, Image.fromarray(frame_rgb)))
            
            cap.release()
            return frames
            
        except Exception as e:
            print(f"Error extracting keyframes: {e}")
            return []
    
    def load_moondream_model(self):
        """Load Moondream2 model for frame descriptions"""
        if self.moondream_model is not None:
            return self.moondream_tokenizer, self.moondream_model
        
        try:
            print(f"\nLoading Moondream2 model...\n")
            
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            self.moondream_tokenizer = AutoTokenizer.from_pretrained(
                "vikhyatk/moondream2", 
                trust_remote_code=True
            )
            
            self.moondream_model = AutoModelForCausalLM.from_pretrained(
                "vikhyatk/moondream2",
                trust_remote_code=True,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            ).to(self.device)
            
            self.moondream_model.eval()
            print("Moondream2 model loaded successfully!\n")
            return self.moondream_tokenizer, self.moondream_model
            
        except Exception as e:
            print(f"Failed to load Moondream2 model: {e}")
            return None, None
    
    def load_llm_model(self, model_name):
        """Load the selected LLM model"""
        if model_name == "none":
            return None, None
        
        if self.llm_model is not None:
            return self.llm_tokenizer, self.llm_model
        
        try:
            print(f"\nLoading LLM model: {model_name}...\n")
            
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            model_map = {
                "phi-3-mini-4k": "microsoft/Phi-3-mini-4k-instruct",
                "qwen2.5-7b": "Qwen/Qwen2.5-7B-Instruct",
                "mistral-7b": "mistralai/Mistral-7B-Instruct-v0.2",
            }
            
            model_id = model_map.get(model_name, "microsoft/Phi-3-mini-4k-instruct")
            
            # Load tokenizer
            self.llm_tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                trust_remote_code=True
            )
            
            # Set padding token if needed
            if self.llm_tokenizer.pad_token is None:
                self.llm_tokenizer.pad_token = self.llm_tokenizer.eos_token
            
            # Load model
            self.llm_model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
                trust_remote_code=True,
            )
            
            print(f"LLM model {model_name} loaded successfully!\n")
            return self.llm_tokenizer, self.llm_model
            
        except Exception as e:
            print(f"Failed to load LLM model: {e}")
            print("\nNote: Some models may require Hugging Face authentication.")
            print("Try running: huggingface-cli login")
            return None, None
    
    def describe_frame(self, image, tokenizer, model):
        """Generate description for a single frame using Moondream2"""
        try:
            enc_image = model.encode_image(image)
            
            question = "Describe this image in detail, including setting, characters, actions, and mood."
            with torch.no_grad():
                answer = model.answer_question(enc_image, question, tokenizer)
            
            caption = answer.strip()
            
            # Clean up the response
            patterns_to_remove = [
                question,
                f"{question}:",
                f"Question: {question}",
                f"Q: {question}",
                "Answer:",
                "A:",
            ]
            
            for pattern in patterns_to_remove:
                if caption.lower().startswith(pattern.lower()):
                    caption = caption[len(pattern):].lstrip(" :-\n")
                    break
            
            return caption.strip()
            
        except Exception as e:
            print(f"Error describing frame: {e}")
            return "Unable to describe this frame."
    
    def summarize_with_llm(self, frame_descriptions, tokenizer, model, max_length=500):
        """Summarize multiple frame descriptions into a video caption using LLM"""
        try:
            # Prepare concise prompt with frame descriptions
            descriptions_text = "\n".join([
                f"At {time:.1f}s: {desc[:150]}{'...' if len(desc) > 150 else ''}"
                for time, desc in frame_descriptions
            ])
            
            prompt = f"""Based on these key moments from a video scene, write a comprehensive caption describing the entire scene:

{descriptions_text}

Write a detailed caption that captures:
- The setting/location
- Characters/people present
- Actions/activities happening
- Changes over time
- Overall mood/atmosphere

Video caption:"""
            
            # Tokenize
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(self.device)
            
            # Calculate available tokens
            input_length = inputs['input_ids'].shape[1]
            max_new_tokens = min(400, 4096 - input_length)
            
            if max_new_tokens < 100:
                # Prompt too long, use fallback
                raise ValueError("Prompt too long for model context")
            
            # FIX for Phi-3: Use generate with updated parameters
            with torch.no_grad():
                # Try different generation methods
                try:
                    outputs = model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        temperature=0.3,
                        do_sample=True,
                        top_p=0.9,
                        repetition_penalty=1.1,
                        pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
                except AttributeError as e:
                    if "'DynamicCache' object has no attribute 'seen_tokens'" in str(e):
                        # Alternative generation for Phi-3
                        print("Using alternative generation for Phi-3...")
                        outputs = model.generate(
                            input_ids=inputs['input_ids'],
                            attention_mask=inputs['attention_mask'],
                            max_new_tokens=max_new_tokens,
                            temperature=0.3,
                            do_sample=True,
                            top_p=0.9,
                            pad_token_id=tokenizer.pad_token_id,
                            eos_token_id=tokenizer.eos_token_id,
                        )
                    else:
                        raise
            
            # Decode response
            full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Extract only the new text (after prompt)
            if prompt in full_response:
                response = full_response[len(prompt):].strip()
            else:
                response = full_response
            
            # Clean up
            response = response.split("\n\n")[0].strip()
            
            # Ensure proper ending
            if response and not response.endswith(('.', '!', '?')):
                last_period = response.rfind('.')
                if last_period > len(response) * 0.7:
                    response = response[:last_period + 1]
            
            return response
            
        except Exception as e:
            print(f"LLM summarization failed: {e}")
            raise
    
    def smart_summarize(self, frame_descriptions, max_length=500):
        """Intelligent summarization without LLM"""
        try:
            if not frame_descriptions:
                return "No frames to describe."
            
            descriptions = [desc for _, desc in frame_descriptions]
            
            # Use the most detailed description as base
            base_desc = max(descriptions, key=len)
            
            # Check if scenes change
            if len(frame_descriptions) > 1:
                first_desc = descriptions[0]
                last_desc = descriptions[-1]
                
                # Simple similarity check
                first_words = set(first_desc.lower().split()[:15])
                last_words = set(last_desc.lower().split()[:15])
                overlap = len(first_words.intersection(last_words)) / max(len(first_words), 1)
                
                if overlap < 0.6:  # Significant change
                    base_desc += " The scene evolves with changing compositions."
                else:
                    base_desc += " The scene remains consistent throughout."
            
            # Ensure proper length
            if len(base_desc) > max_length:
                # Try to end at sentence boundary
                for end_char in ['.', '!', '?']:
                    last_end = base_desc[:max_length].rfind(end_char)
                    if last_end > max_length * 0.7:
                        return base_desc[:last_end + 1]
                
                # Fallback to word boundary
                return base_desc[:max_length].rsplit(' ', 1)[0] + "..."
            
            return base_desc
            
        except Exception as e:
            print(f"Smart summarization error: {e}")
            return frame_descriptions[0][1] if frame_descriptions else "Scene description unavailable."
    
    def find_video_files(self, directory):
        """Find video files in directory"""
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}
        video_files = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if os.path.splitext(file)[1].lower() in video_extensions:
                    video_files.append(os.path.join(root, file))
        
        # Sort by filename
        video_files.sort()
        return video_files
    
    def get_video_url_for_frontend(self, video_path):
        """Generate URL for video to be accessed by frontend"""
        try:
            # Get absolute path
            abs_video_path = os.path.abspath(video_path)
            
            # Check if file exists
            if not os.path.exists(abs_video_path):
                return None, f"File does not exist: {abs_video_path}"
            
            # Check if it's a file
            if not os.path.isfile(abs_video_path):
                return None, f"Path is not a file: {abs_video_path}"
            
            # Get file size
            file_size = os.path.getsize(abs_video_path)
            
            # URL encode the path - important for special characters
            encoded_path = urllib.parse.quote(abs_video_path, safe='')
            
            # Use the viewer endpoint with full path
            url = f"/video_scene/viewer/read_video?filepath={encoded_path}"
            
            return url, f"File exists: {abs_video_path} ({file_size:,} bytes)"
            
        except Exception as e:
            error_msg = f"Error generating video URL: {str(e)}"
            print(error_msg)
            
            # Fallback: try to get relative path
            try:
                output_dir = folder_paths.get_output_directory()
                if output_dir:
                    abs_output_dir = os.path.abspath(output_dir)
                    if abs_video_path.startswith(abs_output_dir):
                        rel_path = os.path.relpath(abs_video_path, abs_output_dir)
                        encoded_rel_path = urllib.parse.quote(rel_path, safe='')
                        url = f"/video_scene/read_video?path={encoded_rel_path}"
                        return url, f"Using relative path from output directory: {rel_path}"
            except Exception as e2:
                error_msg += f" | Fallback failed: {str(e2)}"
            
            return None, error_msg
    
    def generate_captions(self, scene_video_paths, llm_model, sampling_interval,
                         max_frames, max_description_length, selected_scene_index,
                         use_cache, video_scenes_output_path=""):
        
        print(f"\n{'='*60}")
        print(f"VideoSceneCaption: Starting caption generation")
        print(f"Selected scene index: {selected_scene_index}")
        print(f"LLM model: {llm_model}")
        print(f"{'='*60}")
        
        # Initialize debug information
        debug_info_lines = []
        debug_info_lines.append(f"VideoSceneCaption Debug Information")
        debug_info_lines.append(f"{'='*60}")
        debug_info_lines.append(f"Selected scene index: {selected_scene_index}")
        debug_info_lines.append(f"Total input video paths: {len(scene_video_paths) if scene_video_paths else 0}")
        
        # Determine output directory - IMPORTANT: Use scene_outputs as base
        if video_scenes_output_path and os.path.exists(video_scenes_output_path):
            # Use VideoSceneExtractor's output directory
            base_dir = video_scenes_output_path
            debug_info_lines.append(f"✓ Using VideoSceneExtractor output as base: {base_dir}")
            
            # If base_dir doesn't end with scene_outputs, add it
            if not base_dir.endswith("scene_outputs"):
                base_dir = os.path.join(base_dir, "scene_outputs")
                debug_info_lines.append(f"  Adjusted to: {base_dir}")
        else:
            # Use default output directory with scene_outputs subdirectory
            base_dir = folder_paths.get_output_directory()
            scene_outputs_dir = os.path.join(base_dir, "scene_outputs")
            base_dir = scene_outputs_dir
            debug_info_lines.append(f"Using default scene_outputs directory: {base_dir}")
        
        # Create captions subdirectory under scene_outputs
        captions_dir = os.path.join(base_dir, "scene_captions")
        os.makedirs(captions_dir, exist_ok=True)
        
        debug_info_lines.append(f"Captions directory: {captions_dir}")
        debug_info_lines.append(f"Base directory: {base_dir}")
        
        # Get video files
        valid_video_paths = []
        if scene_video_paths and len(scene_video_paths) > 0:
            # Use provided video paths
            valid_video_paths = [p for p in scene_video_paths if p and os.path.exists(p)]
            debug_info_lines.append(f"Using {len(valid_video_paths)} provided video paths")
            
            # Log the first few paths
            for i, path in enumerate(valid_video_paths[:5]):
                abs_path = os.path.abspath(path)
                exists = os.path.exists(abs_path)
                debug_info_lines.append(f"  Video {i+1}: {abs_path} ({'Exists' if exists else 'MISSING'})")
            if len(valid_video_paths) > 5:
                debug_info_lines.append(f"  ... and {len(valid_video_paths) - 5} more")
        else:
            # Auto-discover video files in scene_outputs/videos
            print("No video paths provided, searching for videos...")
            debug_info_lines.append("No video paths provided, searching for videos...")
            
            # Check in scene_outputs/videos directory
            videos_dir = os.path.join(base_dir, "videos")
            if os.path.exists(videos_dir):
                valid_video_paths = self.find_video_files(videos_dir)
                debug_info_lines.append(f"Found {len(valid_video_paths)} videos in: {videos_dir}")
            else:
                # Fallback to searching in base directory
                valid_video_paths = self.find_video_files(base_dir)
                debug_info_lines.append(f"Found {len(valid_video_paths)} videos in: {base_dir}")
        
        if not valid_video_paths:
            debug_info_lines.append("ERROR: No valid video files found")
            print("Error: No valid video files found")
            return self.return_empty(captions_dir, selected_scene_index)
        
        debug_info_lines.append(f"Found {len(valid_video_paths)} valid video files")
        
        # Generate cache key
        cache_key_params = f"{len(valid_video_paths)}_{llm_model}_{sampling_interval}_{max_frames}_{max_description_length}_{base_dir}"
        cache_key = hashlib.md5(cache_key_params.encode()).hexdigest()[:16]
        
        cache_file = os.path.join(captions_dir, f"cache_{cache_key}.json")
        
        # Check cache
        scene_captions = []
        metadata = {
            "base_directory": base_dir,
            "captions_directory": captions_dir,
            "llm_model": llm_model,
            "sampling_interval": sampling_interval,
            "max_frames": max_frames,
            "max_description_length": max_description_length,
            "total_scenes": len(valid_video_paths),
            "scenes": []
        }
        
        # Check if we can use cache
        video_paths_changed = self.last_video_paths != valid_video_paths
        cache_valid = False
        
        if use_cache and os.path.exists(cache_file) and not video_paths_changed:
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                scene_captions = cached_data.get("scene_captions", [])
                metadata = cached_data.get("metadata", metadata)
                
                # Validate cache
                if len(scene_captions) == len(valid_video_paths):
                    cache_valid = True
                    debug_info_lines.append(f"✓ Loaded {len(scene_captions)} cached captions")
                else:
                    debug_info_lines.append(f"Cache invalid: expected {len(valid_video_paths)} captions, got {len(scene_captions)}")
                    scene_captions = []
            except Exception as e:
                debug_info_lines.append(f"Error loading cache: {e}")
        
        # Update tracking
        self.last_video_paths = valid_video_paths
        self.last_index = selected_scene_index
        
        # Generate video URLs for frontend with detailed debugging
        scene_video_urls = []
        video_debug_info = []
        
        debug_info_lines.append(f"\nVideo URL Generation:")
        debug_info_lines.append(f"{'-'*40}")
        
        for i, video_path in enumerate(valid_video_paths):
            abs_video_path = os.path.abspath(video_path)
            debug_info_lines.append(f"\nScene {i+1}:")
            debug_info_lines.append(f"  Input path: {video_path}")
            debug_info_lines.append(f"  Absolute path: {abs_video_path}")
            debug_info_lines.append(f"  File exists: {os.path.exists(abs_video_path)}")
            
            if os.path.exists(abs_video_path):
                file_size = os.path.getsize(abs_video_path)
                debug_info_lines.append(f"  File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
                debug_info_lines.append(f"  Is file: {os.path.isfile(abs_video_path)}")
                
                # Generate URL
                video_url, url_debug = self.get_video_url_for_frontend(video_path)
                scene_video_urls.append(video_url)
                
                if video_url:
                    debug_info_lines.append(f"  ✓ URL generated: {video_url}")
                else:
                    debug_info_lines.append(f"  ✗ URL generation failed")
                
                debug_info_lines.append(f"  Debug: {url_debug}")
                
                # Store detailed debug info for this video
                video_debug_info.append({
                    "scene_index": i,
                    "input_path": video_path,
                    "absolute_path": abs_video_path,
                    "exists": True,
                    "file_size": file_size,
                    "url": video_url,
                    "debug": url_debug
                })
            else:
                debug_info_lines.append(f"  ✗ FILE NOT FOUND")
                scene_video_urls.append(None)
                video_debug_info.append({
                    "scene_index": i,
                    "input_path": video_path,
                    "absolute_path": abs_video_path,
                    "exists": False,
                    "file_size": 0,
                    "url": None,
                    "debug": "File does not exist"
                })
        
        # Add URL summary
        successful_urls = sum(1 for url in scene_video_urls if url)
        debug_info_lines.append(f"\nURL Generation Summary:")
        debug_info_lines.append(f"  Total videos: {len(valid_video_paths)}")
        debug_info_lines.append(f"  Successful URLs: {successful_urls}")
        debug_info_lines.append(f"  Failed URLs: {len(valid_video_paths) - successful_urls}")
        
        if not cache_valid:
            # Load Moondream2
            debug_info_lines.append(f"\nLoading Moondream2 model...")
            moondream_tokenizer, moondream_model = self.load_moondream_model()
            if not moondream_model:
                debug_info_lines.append(f"Failed to load Moondream2 model")
                print("Failed to load Moondream2 model")
                return self.return_empty(captions_dir, selected_scene_index)
            
            # Load LLM if not "none"
            llm_tokenizer = None
            llm_model_obj = None
            use_llm = llm_model != "none"
            
            if use_llm:
                debug_info_lines.append(f"Loading LLM model: {llm_model}...")
                llm_tokenizer, llm_model_obj = self.load_llm_model(llm_model)
                if not llm_model_obj:
                    debug_info_lines.append("LLM model not available, using smart summarization")
                    use_llm = False
            
            # Process each video
            total_videos = len(valid_video_paths)
            self.create_progress_bar(total_videos, "Generating captions")
            
            for i, video_path in enumerate(valid_video_paths):
                video_filename = os.path.basename(video_path)
                debug_info_lines.append(f"\nProcessing scene {i+1}/{total_videos}: {video_filename}")
                
                # Update progress
                self.update_progress(i + 1, total_videos, f"Scene {i+1}/{total_videos}")
                
                # Get video info
                duration = self.get_video_duration(video_path)
                debug_info_lines.append(f"  Duration: {duration:.2f}s")
                
                # Extract keyframes throughout the video
                frames = self.extract_keyframes(video_path, sampling_interval, max_frames)
                debug_info_lines.append(f"  Extracted {len(frames)} keyframes")
                
                if not frames:
                    caption = "No frames extracted from video."
                    scene_captions.append(caption)
                    metadata["scenes"].append({
                        "index": i,
                        "video_path": video_path,
                        "video_filename": video_filename,
                        "video_url": scene_video_urls[i] if i < len(scene_video_urls) else None,
                        "duration": duration,
                        "keyframes": 0,
                        "caption": caption,
                        "method": "error"
                    })
                    debug_info_lines.append(f"  ✗ Failed to extract frames")
                    continue
                
                # Describe each frame with Moondream2
                frame_descriptions = []
                for frame_idx, (timestamp, frame_image) in enumerate(frames):
                    debug_info_lines.append(f"    Describing frame {frame_idx+1}/{len(frames)} at {timestamp:.1f}s...")
                    description = self.describe_frame(frame_image, moondream_tokenizer, moondream_model)
                    frame_descriptions.append((timestamp, description))
                
                # Generate video caption
                video_caption = ""
                method_used = ""
                
                if use_llm and llm_model_obj and len(frame_descriptions) > 1:
                    try:
                        debug_info_lines.append(f"  Generating caption with {llm_model}...")
                        video_caption = self.summarize_with_llm(
                            frame_descriptions, 
                            llm_tokenizer, 
                            llm_model_obj,
                            max_length=max_description_length
                        )
                        method_used = f"llm_{llm_model}"
                    except Exception as e:
                        debug_info_lines.append(f"  LLM failed: {e}")
                        debug_info_lines.append("  Falling back to smart summarization...")
                        video_caption = self.smart_summarize(frame_descriptions, max_description_length)
                        method_used = "smart_fallback"
                else:
                    debug_info_lines.append(f"  Using smart summarization...")
                    video_caption = self.smart_summarize(frame_descriptions, max_description_length)
                    method_used = "smart" if llm_model == "none" else "smart_fallback"
                
                # Final cleanup
                video_caption = video_caption.strip()
                if len(video_caption) > max_description_length:
                    video_caption = video_caption[:max_description_length].rsplit(' ', 1)[0] + "..."
                
                scene_captions.append(video_caption)
                
                # Save individual caption file - ALWAYS in scene_captions directory
                caption_filename = f"scene_{i:04d}_caption.txt"
                caption_filepath = os.path.join(captions_dir, caption_filename)
                with open(caption_filepath, 'w', encoding='utf-8') as f:
                    f.write(video_caption + '\n')
                
                # Add to metadata
                metadata["scenes"].append({
                    "index": i,
                    "video_path": video_path,
                    "video_filename": video_filename,
                    "video_url": scene_video_urls[i] if i < len(scene_video_urls) else None,
                    "duration": duration,
                    "keyframes_extracted": len(frames),
                    "frame_descriptions": [
                        {"timestamp": ts, "description": desc[:100] + "..." if len(desc) > 100 else desc}
                        for ts, desc in frame_descriptions
                    ],
                    "caption": video_caption,
                    "caption_file": caption_filename,
                    "caption_filepath": caption_filepath,  # Store the full path for easy reference
                    "method": method_used
                })
                
                debug_info_lines.append(f"  ✓ Caption saved: {caption_filename}")
                debug_info_lines.append(f"  Caption length: {len(video_caption)} characters")
                debug_info_lines.append(f"  Saved to: {caption_filepath}")
            
            # Cache results
            if use_cache:
                cache_data = {
                    "scene_captions": scene_captions,
                    "metadata": metadata,
                    "cache_key": cache_key
                }
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                debug_info_lines.append(f"\n✓ Results cached: {cache_file}")
            
            # Clean up models
            debug_info_lines.append("\nCleaning up models...")
            if moondream_model:
                del moondream_model
                self.moondream_model = None
                self.moondream_tokenizer = None
            
            if llm_model_obj:
                del llm_model_obj
                self.llm_model = None
                self.llm_tokenizer = None
            
            torch.cuda.empty_cache()
        
        # Save metadata
        metadata_path = os.path.join(captions_dir, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        debug_info_lines.append(f"\nMetadata saved: {metadata_path}")
        
        # Get selected caption
        internal_index = selected_scene_index - 1  # Convert 1-based to 0-based
        selected_caption = ""
        
        if 0 <= internal_index < len(scene_captions):
            selected_caption = scene_captions[internal_index]
            debug_info_lines.append(f"\nSelected caption (scene {selected_scene_index}):")
            debug_info_lines.append(f"  {selected_caption[:200]}...")
        elif scene_captions:
            selected_caption = scene_captions[0]
            internal_index = 0
            debug_info_lines.append(f"\nSelected index out of bounds, using first caption")
        
        # Add final summary to debug info
        debug_info_lines.append(f"\n{'='*60}")
        debug_info_lines.append(f"✓ Complete! Generated {len(scene_captions)} scene captions")
        debug_info_lines.append(f"  Output directory: {captions_dir}")
        debug_info_lines.append(f"  Selected scene: {selected_scene_index} (internal: {internal_index})")
        debug_info_lines.append(f"  Selected caption length: {len(selected_caption)} characters")
        debug_info_lines.append(f"  Video URLs generated: {len([url for url in scene_video_urls if url])}/{len(valid_video_paths)}")
        debug_info_lines.append(f"  Base directory for saving: {base_dir}")
        debug_info_lines.append(f"  Captions saved in: {captions_dir}")
        
        # Compile final debug info
        debug_info = "\n".join(debug_info_lines)
        
        # Print summary to console
        print(f"\n{'='*60}")
        print(f"✓ Complete! Generated {len(scene_captions)} scene captions")
        print(f"  Base directory: {base_dir}")
        print(f"  Captions directory: {captions_dir}")
        print(f"  Selected scene: {selected_scene_index}")
        print(f"  Video URLs generated: {len([url for url in scene_video_urls if url])}/{len(valid_video_paths)}")
        
        # Also print the selected video's details
        if 0 <= internal_index < len(valid_video_paths):
            selected_video_path = valid_video_paths[internal_index]
            selected_video_url = scene_video_urls[internal_index] if internal_index < len(scene_video_urls) else None
            abs_path = os.path.abspath(selected_video_path)
            exists = os.path.exists(abs_path)
            
            print(f"\nSelected Video Details:")
            print(f"  Path: {selected_video_path}")
            print(f"  Absolute path: {abs_path}")
            print(f"  File exists: {exists}")
            if exists:
                print(f"  File size: {os.path.getsize(abs_path):,} bytes")
            print(f"  URL: {selected_video_url}")
        
        print(f"{'='*60}")
        
        # Return results with video URLs for frontend
        return {
            "ui": {
                "text": [selected_caption],  # Selected caption for display
                "scene_captions": [scene_captions],  # All captions
                "scene_video_paths": [valid_video_paths],  # Video paths
                "scene_video_urls": [scene_video_urls],  # Video URLs for frontend
                "total_scenes": [len(scene_captions)],
                "selected_index": [selected_scene_index],
                "captions_dir": [captions_dir],  # The directory where captions are saved
                "base_dir": [base_dir],  # The base directory (scene_outputs)
                "debug_info": [debug_info],  # Debug info for display
            },
            "result": (captions_dir, scene_captions, json.dumps(metadata, indent=2), selected_caption, debug_info)
        }
    
    def return_empty(self, output_dir, selected_scene_index):
        """Return empty results"""
        debug_info = f"No video files found to process.\nOutput directory: {output_dir}\nSelected scene index: {selected_scene_index}"
        
        return {
            "ui": {
                "text": [""],
                "scene_captions": [[]],
                "scene_video_paths": [[]],
                "scene_video_urls": [[]],
                "total_scenes": [0],
                "selected_index": [selected_scene_index],
                "captions_dir": [output_dir],
                "base_dir": [output_dir],
                "debug_info": [debug_info],
            },
            "result": (output_dir, [], "{}", "", debug_info)
        }

# Register the node
NODE_CLASS_MAPPINGS = {
    "VideoSceneCaption": VideoSceneCaption,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneCaption": "🎬 Video Scene Caption",
}