import os
import cv2
import torch
import folder_paths
from PIL import Image
from transformers import AutoTokenizer, AutoModelForCausalLM
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
import comfy.utils


class VideoSceneGenerationNode:
    """
    A ComfyUI node that detects scenes in a video, extracts keyframes,
    and generates text descriptions using Moondream2 vision model.
    """
    
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
                "output_folder": ("STRING", {
                    "default": "scene_outputs",
                    "multiline": False
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
    def VALIDATE_INPUTS(cls, video_path, **kwargs):
        """Validate that the video file exists and is accessible"""
        if not video_path or not video_path.strip():
            return "Video path cannot be empty"
        
        if not os.path.exists(video_path):
            return f"Video file not found: {video_path}"
        
        # Check if it's a supported video format
        valid_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.mpg', '.mpeg')
        if not video_path.lower().endswith(valid_extensions):
            return f"Unsupported video format. Supported formats: {', '.join(valid_extensions)}"
        
        return True
    
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompts_text", "status_message", "keyframes_path")
    FUNCTION = "generate_scene_prompts"
    CATEGORY = "video/analysis"
    OUTPUT_NODE = True
    
    def load_model(self):
        """Lazy load the Moondream2 model"""
        if self.model is None:
            try:
                print("Loading Moondream2 model...")
                model_path = "vikhyatk/moondream2"
                
                # Load tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(
                    model_path,
                    trust_remote_code=True
                )
                
                # Load model
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    trust_remote_code=True,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
                ).to(self.device)
                
                self.model.eval()
                print(f"Model loaded successfully on {self.device}")
            except Exception as e:
                raise RuntimeError(f"Failed to load Moondream2 model: {str(e)}")
    
    def detect_scenes(self, video_path, threshold=27.0):
        """Detect scene changes in video"""
        try:
            vm = VideoManager([video_path])
            sm = SceneManager()
            sm.add_detector(ContentDetector(threshold=threshold))
            
            vm.start()
            sm.detect_scenes(frame_source=vm)
            scenes = sm.get_scene_list()
            vm.release()
            
            return scenes
        except Exception as e:
            raise RuntimeError(f"Scene detection failed: {str(e)}")
    
    def extract_keyframes(self, video_path, scenes, keyframe_dir):
        """Extract keyframe from each scene"""
        keyframes = []
        
        try:
            cap = cv2.VideoCapture(video_path)
            total_scenes = len(scenes)
            
            pbar = comfy.utils.ProgressBar(total_scenes)
            
            for idx, scene in enumerate(scenes, start=1):
                start_frame = scene[0].get_frames()
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                ret, frame = cap.read()
                
                if not ret:
                    print(f"Warning: Could not read frame for scene {idx}")
                    pbar.update(1)
                    continue
                
                img_path = os.path.join(keyframe_dir, f"scene_{idx:03d}.png")
                cv2.imwrite(img_path, frame)
                keyframes.append(img_path)
                
                pbar.update(1)
            
            cap.release()
            return keyframes
            
        except Exception as e:
            raise RuntimeError(f"Keyframe extraction failed: {str(e)}")
    
    def generate_descriptions(self, keyframes, max_length, style, lighting):
        """Generate text descriptions for keyframes using Moondream2"""
        self.load_model()
        prompts = []
        total_keyframes = len(keyframes)
        
        pbar = comfy.utils.ProgressBar(total_keyframes)
        
        for idx, img_path in enumerate(keyframes, start=1):
            try:
                # Load and convert image to PIL
                pil_image = Image.open(img_path).convert("RGB")
                
                # Encode image using Moondream2's encode_image method
                enc_image = self.model.encode_image(pil_image)
                
                # Generate description using answer_question method
                with torch.no_grad():
                    try:
                        # Try with max_tokens parameter first
                        answer = self.model.answer_question(
                            enc_image,
                            "Describe this scene in detail.",
                            self.tokenizer,
                            max_tokens=max_length
                        )
                    except TypeError:
                        # Fallback without max_tokens if not supported
                        answer = self.model.answer_question(
                            enc_image,
                            "Describe this scene in detail.",
                            self.tokenizer
                        )
                
                # Clean up the answer
                description = answer.strip()
                
                # Remove question echo if present
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
                
                # Remove answer prefixes
                if description.lower().startswith("answer:"):
                    description = description[7:].strip()
                elif description.lower().startswith("a:"):
                    description = description[2:].strip()
                
                # Format prompt with style and lighting
                prompt = f"Image style: {style}. Image lighting: {lighting}. {description}."
                prompts.append(prompt)
                
                print(f"Generated prompt for scene {idx}/{total_keyframes}")
                
            except Exception as e:
                print(f"Error generating description for scene {idx}: {str(e)}")
                import traceback
                traceback.print_exc()
                prompts.append(f"[Error processing scene {idx}]")
            
            pbar.update(1)
        
        return prompts
    
    def generate_scene_prompts(self, video_path, output_folder, style, 
                              lighting, max_description_length, 
                              scene_threshold):
        """Main processing function"""
        
        # Validate video file (additional check)
        if not video_path or not os.path.exists(video_path):
            return ("", f"Error: Video file not found: {video_path}")
        
        try:
            # Create output directories
            os.makedirs(output_folder, exist_ok=True)
            keyframe_dir = os.path.join(output_folder, "keyframes")
            os.makedirs(keyframe_dir, exist_ok=True)
            
            # Detect scenes
            print(f"Processing video: {video_path}")
            print("Detecting scenes...")
            scenes = self.detect_scenes(video_path, scene_threshold)
            
            if not scenes:
                return ("", "Warning: No scenes detected in video")
            
            print(f"Detected {len(scenes)} scenes")
            
            # Extract keyframes
            print("Extracting keyframes...")
            keyframes = self.extract_keyframes(video_path, scenes, keyframe_dir)
            
            if not keyframes:
                return ("", "Error: Failed to extract keyframes")
            
            # Generate descriptions
            print("Generating scene descriptions...")
            prompts = self.generate_descriptions(
                keyframes,
                max_description_length,
                style,
                lighting
            )
            
            # Save individual prompt files alongside each keyframe
            print("Saving individual prompt files...")
            for idx, (keyframe_path, prompt) in enumerate(zip(keyframes, prompts), start=1):
                # Get the base name without extension (e.g., "scene_001")
                base_name = os.path.splitext(os.path.basename(keyframe_path))[0]
                # Create corresponding text file path
                prompt_txt_path = os.path.join(keyframe_dir, f"{base_name}.txt")
                
                # Save individual prompt
                with open(prompt_txt_path, "w", encoding="utf-8") as f:
                    f.write(prompt)
            
            # Also save combined prompts file for reference
            prompt_file = os.path.join(output_folder, "scene_prompts.txt")
            with open(prompt_file, "w", encoding="utf-8") as f:
                for idx, prompt in enumerate(prompts, start=1):
                    f.write(f"Scene {idx}: {prompt}\n\n")
            
            # Format output
            prompts_text = "\n\n".join([
                f"Scene {idx}: {prompt}" 
                for idx, prompt in enumerate(prompts, start=1)
            ])
            
            status_message = (
                f"Success! Processed {len(scenes)} scenes from:\n"
                f"{video_path}\n\n"
                f"Keyframes and prompts saved to: {keyframe_dir}\n"
                f"Combined prompts saved to: {prompt_file}"
            )
            
            return (prompts_text, status_message, keyframe_dir)
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return ("", error_msg, "")


# Node registration for ComfyUI
NODE_CLASS_MAPPINGS = {
    "VideoSceneGenerationNode": VideoSceneGenerationNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneGenerationNode": "Video Scene Analysis & Prompt Generation"
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]