import os
import cv2
import torch
import folder_paths
from PIL import Image
from transformers import AutoTokenizer, AutoModelForCausalLM
from scenedetect import SceneManager, open_video
from scenedetect.detectors import ContentDetector
from scenedetect.frame_timecode import FrameTimecode
import comfy.utils


class VideoSceneGenerationOpenVideoNode:
    
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "dynamicPrompts": False
                }),
                "output_subfolder": ("STRING", {
                    "default": "scene_analysis",
                    "multiline": False
                }),
                "start_time_minutes": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 1000.0,
                    "step": 0.5,
                    "display": "start_time"
                }),
                "end_time_minutes": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 1000.0,
                    "step": 0.5,
                    "display": "end_time"
                }),
                "style": ([
                    "realistic",
                    "anime", 
                    "cartoon",
                    "cartoon comic",
                    "comic",
                    "watercolor",
                    "oil painting",
                    "digital art",
                    "cyberpunk",
                    "fantasy art",
                    "photorealistic"
                ], {
                    "default": "realistic"
                }),
                "lighting": ([
                    "soft",
                    "hard",
                    "natural",
                    "dramatic",
                    "studio",
                    "golden hour",
                    "blue hour",
                    "backlit",
                    "rim lighting",
                    "low key",
                    "high key",
                    "ambient",
                    "moody",
                    "bright",
                    "dark",
                    "neon",
                    "cinematic"
                ], {
                    "default": "soft"
                }),
                "max_description_length": ("INT", {
                    "default": 512,
                    "min": 16,
                    "max": 1024,
                    "step": 16
                }),
                "scene_threshold": ("FLOAT", {
                    "default": 27.0,
                    "min": 1.0,
                    "max": 100.0,
                    "step": 1.0
                })
            }
        }
    
    @classmethod
    def VALIDATE_INPUTS(cls, video_path, start_time_minutes, end_time_minutes, **kwargs):
        if not video_path or not video_path.strip():
            return "Video path cannot be empty"
        
        if not os.path.exists(video_path):
            return f"Video file not found: {video_path}"
        
        valid_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg')
        if not video_path.lower().endswith(valid_extensions):
            return f"Unsupported video format. Supported formats: {', '.join(valid_extensions)}"
        
        if end_time_minutes > 0 and end_time_minutes <= start_time_minutes:
            return "End time must be greater than start time"
        
        return True
    
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompts_text", "status_message", "keyframes_path")
    FUNCTION = "generate_scene_prompts"
    CATEGORY = "video/analysis"
    OUTPUT_NODE = True
    
    def sanitize_path(self, subfolder_path):
        import re
        
        subfolder_path = subfolder_path.strip()
        
        subfolder_path = re.sub(r'^[\/\.]+', '', subfolder_path)
        
        parts = []
        for part in subfolder_path.split('/'):
            clean_part = re.sub(r'[\\:*?"<>|]', '', part)
            clean_part = clean_part.strip('.')
            
            if not clean_part or clean_part == '..' or clean_part == '.':
                continue
            
            parts.append(clean_part)
        
        safe_path = '/'.join(parts)
        
        if not safe_path:
            safe_path = "scene_analysis"
        
        return safe_path
    
    def load_model(self):
        if self.model is None:
            try:
                print("Loading Moondream2 model...")
                model_path = "vikhyatk/moondream2"
                
                self.tokenizer = AutoTokenizer.from_pretrained(
                    model_path,
                    trust_remote_code=True
                )
                
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    trust_remote_code=True,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
                ).to(self.device)
                
                self.model.eval()
                print(f"Model loaded successfully on {self.device}")
            except Exception as e:
                raise RuntimeError(f"Failed to load Moondream2 model: {str(e)}")
    
    def detect_scenes(self, video_path, threshold=27.0, start_time_seconds=None, end_time_seconds=None):
        try:
            video_stream = open_video(video_path)
            fps = video_stream.frame_rate
            
            print(f"Video FPS: {fps}")
            
            sm = SceneManager()
            sm.add_detector(ContentDetector(threshold=threshold))
            
            sm.detect_scenes(video=video_stream)
            all_scenes = sm.get_scene_list()
            
            scenes = []
            for scene in all_scenes:
                scene_start = scene[0].get_seconds()
                scene_end = scene[1].get_seconds()
                
                include_scene = True
                if start_time_seconds is not None and scene_end < start_time_seconds:
                    include_scene = False
                if end_time_seconds is not None and scene_start > end_time_seconds:
                    include_scene = False
                
                if include_scene:
                    scenes.append(scene)
            
            return scenes
            
        except Exception as e:
            raise RuntimeError(f"Scene detection failed: {str(e)}")
    
    def extract_keyframes(self, video_path, scenes, keyframe_dir):
        keyframes = []
        
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            total_scenes = len(scenes)
            pbar = comfy.utils.ProgressBar(total_scenes)
            
            for idx, scene in enumerate(scenes, start=1):
                scene_start_frame = scene[0].get_frames()
                cap.set(cv2.CAP_PROP_POS_FRAMES, scene_start_frame)
                ret, frame = cap.read()
                
                if not ret:
                    print(f"Warning: Could not read frame for scene {idx}")
                    pbar.update(1)
                    continue
                
                timestamp_seconds = scene_start_frame / fps
                minutes = int(timestamp_seconds // 60)
                seconds = int(timestamp_seconds % 60)
                milliseconds = int((timestamp_seconds - int(timestamp_seconds)) * 1000)
                
                img_path = os.path.join(keyframe_dir, f"scene_{idx:03d}_{minutes:02d}m{seconds:02d}s{milliseconds:03d}ms.png")

                cv2.imwrite(img_path, frame)
                keyframes.append(img_path)
                
                print(f"Extracted scene {idx} at {minutes:02d}:{seconds:02d}.{milliseconds:03d}")
                pbar.update(1)
            
            cap.release()
            return keyframes
            
        except Exception as e:
            raise RuntimeError(f"Keyframe extraction failed: {str(e)}")
    
    def generate_descriptions(self, keyframes, max_length, style, lighting):
        self.load_model()
        prompts = []
        total_keyframes = len(keyframes)
        
        pbar = comfy.utils.ProgressBar(total_keyframes)
        
        for idx, img_path in enumerate(keyframes, start=1):
            try:
                pil_image = Image.open(img_path).convert("RGB")
                
                enc_image = self.model.encode_image(pil_image)
                
                with torch.no_grad():
                    try:
                        answer = self.model.answer_question(
                            enc_image,
                            "Describe this scene in detail.",
                            self.tokenizer,
                            max_tokens=max_length
                        )
                    except TypeError:
                        answer = self.model.answer_question(
                            enc_image,
                            "Describe this scene in detail.",
                            self.tokenizer
                        )
                
                description = answer.strip()
                
                question = "Describe this scene in detail."
                patterns_to_remove = [
                    question,
                    f"{question}:",
                    f"{question} ",
                    f"Question: {question}",
                    f"Q: {question}",
                ]
                
                for pattern in patterns_to_remove:
                    if description.lower().startswith(pattern.lower()):
                        description = description[len(pattern):].strip()
                        description = description.lstrip(':-').strip()
                        break
                
                if description.lower().startswith("answer:"):
                    description = description[7:].strip()
                elif description.lower().startswith("a:"):
                    description = description[2:].strip()
                
                prompt = f"Image style: {style}. Image lighting: {lighting}. {description}"
                prompts.append(prompt)
                
                print(f"Generated prompt for scene {idx}/{total_keyframes}")
                
            except Exception as e:
                print(f"Error generating description for scene {idx}: {str(e)}")
                import traceback
                traceback.print_exc()
                prompts.append(f"[Error processing scene {idx}]")
            
            pbar.update(1)
        
        return prompts
    
    def generate_scene_prompts(self, video_path, output_subfolder, start_time_minutes, 
                              end_time_minutes, style, lighting, max_description_length, 
                              scene_threshold):
        
        if not video_path or not os.path.exists(video_path):
            return ("", f"Error: Video file not found: {video_path}", "")
        
        start_time_seconds = start_time_minutes * 60
        end_time_seconds = end_time_minutes * 60 if end_time_minutes > 0 else None
        
        if end_time_seconds is not None and end_time_seconds <= start_time_seconds:
            return ("", "Error: End time must be greater than start time", "")
        
        try:
            comfyui_output_dir = folder_paths.get_output_directory()
            
            sanitized_subfolder = self.sanitize_path(output_subfolder)
            
            output_folder = os.path.join(comfyui_output_dir, sanitized_subfolder)
            
            output_folder = os.path.abspath(output_folder)
            comfyui_output_dir = os.path.abspath(comfyui_output_dir)
            
            if not output_folder.startswith(comfyui_output_dir):
                print(f"Security warning: Attempted to write outside output directory: {output_folder}")
                return ("", f"Error: Invalid output path. Must stay within {comfyui_output_dir}", "")
            
            os.makedirs(output_folder, exist_ok=True)
            
            keyframe_dir = os.path.join(output_folder, "keyframes")
            keyframe_dir = os.path.abspath(keyframe_dir)
            
            if not keyframe_dir.startswith(comfyui_output_dir):
                print(f"Security warning: Attempted to write keyframes outside output directory: {keyframe_dir}")
                return ("", f"Error: Invalid keyframes path. Must stay within {comfyui_output_dir}", "")
            
            os.makedirs(keyframe_dir, exist_ok=True)
            
            print(f"Processing video: {video_path}")
            print(f"Output folder: {output_folder}")
            print(f"Keyframes directory: {keyframe_dir}")
            
            if end_time_seconds is not None:
                duration_minutes = (end_time_seconds - start_time_seconds) / 60
                print(f"Time range: {start_time_minutes:.1f}min to {end_time_minutes:.1f}min ({duration_minutes:.1f} minutes)")
            elif start_time_seconds > 0:
                print(f"Starting from: {start_time_minutes:.1f}min")
            else:
                print("Processing entire video")
            
            print("Detecting scenes...")
            scenes = self.detect_scenes(
                video_path, 
                scene_threshold, 
                start_time_seconds, 
                end_time_seconds
            )
            
            if not scenes:
                return ("", "Warning: No scenes detected in the specified time range", keyframe_dir)
            
            print(f"Detected {len(scenes)} scenes")
            
            print("Extracting keyframes...")
            keyframes = self.extract_keyframes(video_path, scenes, keyframe_dir)
            
            if not keyframes:
                return ("", "Error: Failed to extract keyframes", keyframe_dir)
            
            print("Generating scene descriptions...")
            prompts = self.generate_descriptions(
                keyframes,
                max_description_length,
                style,
                lighting
            )
            
            print("Saving individual prompt files...")
            for idx, (keyframe_path, prompt) in enumerate(zip(keyframes, prompts), start=1):
                base_name = os.path.splitext(os.path.basename(keyframe_path))[0]
                prompt_txt_path = os.path.join(keyframe_dir, f"{base_name}.txt")
                
                prompt_txt_path = os.path.abspath(prompt_txt_path)
                if not prompt_txt_path.startswith(comfyui_output_dir):
                    print(f"Security warning: Attempted to write prompt outside output directory: {prompt_txt_path}")
                    continue
                
                with open(prompt_txt_path, "w", encoding="utf-8") as f:
                    f.write(prompt)
            
            prompt_file = os.path.join(output_folder, "scene_prompts.txt")
            prompt_file = os.path.abspath(prompt_file)
            
            if not prompt_file.startswith(comfyui_output_dir):
                print(f"Security warning: Attempted to write prompts file outside output directory: {prompt_file}")
                prompt_file = os.path.join(keyframe_dir, "scene_prompts.txt")
            
            with open(prompt_file, "w", encoding="utf-8") as f:
                for idx, prompt in enumerate(prompts, start=1):
                    f.write(f"Scene {idx}: {prompt}\n\n")
            
            prompts_text = "\n\n".join([
                f"Scene {idx}: {prompt}" 
                for idx, prompt in enumerate(prompts, start=1)
            ])
            
            if end_time_seconds is not None:
                time_info = f"Time range: {start_time_minutes:.1f}min to {end_time_minutes:.1f}min"
            elif start_time_seconds > 0:
                time_info = f"Starting from: {start_time_minutes:.1f}min"
            else:
                time_info = "Processed entire video"
            
            status_message = (
                f"Success! Processed {len(scenes)} scenes from:\n"
                f"{video_path}\n"
                f"{time_info}\n\n"
                f"Keyframes and prompts saved to: {keyframe_dir}\n"
                f"Combined prompts saved to: {prompt_file}"
            )
            
            return (prompts_text, status_message, output_folder)
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return ("", error_msg, "")


NODE_CLASS_MAPPINGS = {
    "VideoSceneGenerationOpenVideoNode": VideoSceneGenerationOpenVideoNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneGenerationOpenVideoNode": "Video Scene Analysis & Prompt Generation - Open Video"
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]