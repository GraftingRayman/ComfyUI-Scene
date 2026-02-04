# VideoSceneCaption.py - Scene video captioning with selected_scene_index and LTX format options
# UPDATED: Now uses 1-based numbering (0001, 0002, etc.) instead of 0-based (0000, 0001)
import os
import torch
import cv2
import numpy as np
from PIL import Image
import folder_paths
import json
import hashlib
import urllib.parse
import re
import time
from typing import List, Union
import warnings
import subprocess
import shutil
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
                    "step": 0.1
                }),
                "max_frames": ("INT", {
                    "default": 6,
                    "min": 3,
                    "max": 12,
                    "step": 1
                }),
                "max_description_length": ("INT", {
                    "default": 2500,
                    "min": 200,
                    "max": 10000,
                    "step": 50,
                }),
                "use_cache": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Use Cache",
                    "label_off": "Force Regenerate"
                }),

                "extract_assets": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Extract Assets",
                    "label_off": "No Assets"
                }),
                "keep_models_loaded": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Keep Models",
                    "label_off": "Unload After Use"
                }),
                "ltx_format": ("BOOLEAN", {
                    "default": False,
                    "label_on": "Enable LTX Format",
                    "label_off": "Standard Format"
                }),
                "ltx_format_type": ([
                    "Standard",
                    "T2V", 
                    "I2V"
                ], {
                    "default": "Standard"
                }),
                "load_existing_files": ("BOOLEAN", {
                    "default": False,
                    "label_on": "Load Existing Files",
                    "label_off": "Process Normally"
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

    RETURN_TYPES = ("STRING", "LIST", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("output_path", "scene_captions", "metadata_json", "selected_caption", "debug_info", 
                   "selected_scene_video", "selected_scene_audio", "selected_scene_video_no_audio", "selected_caption_ltx")
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
        self.debug_dir = None
    
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
    
    def setup_debug_logging(self, base_dir):
        """Setup debug logging directory"""
        debug_dir = os.path.join(base_dir, "debug_logs")
        os.makedirs(debug_dir, exist_ok=True)
        self.debug_dir = debug_dir
        print(f"Debug logs will be saved to: {debug_dir}")
        return debug_dir
    
    def save_debug_info(self, filename, content, scene_number=None, step=None):
        """Save debug information to file"""
        if not self.debug_dir:
            return
        
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            if scene_number is not None and step is not None:
                filename = f"scene_{scene_number:04d}_{step}_{timestamp}_{filename}"
            elif scene_number is not None:
                filename = f"scene_{scene_number:04d}_{timestamp}_{filename}"
            else:
                filename = f"{timestamp}_{filename}"
            
            filepath = os.path.join(self.debug_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                if isinstance(content, dict):
                    json.dump(content, f, indent=2, ensure_ascii=False)
                else:
                    f.write(str(content))
            
            return filepath
        except Exception as e:
            print(f"Warning: Could not save debug info {filename}: {e}")
            return None
    
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
    
    def extract_audio_from_video(self, video_path, output_audio_path):
        """Extract audio from video using ffmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode != 0:
                print("FFmpeg not found, cannot extract audio")
                return None
            
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',
                '-acodec', 'mp3',
                '-ab', '192k',
                '-y',
                output_audio_path
            ]
            
            print(f"Extracting audio from: {os.path.basename(video_path)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_audio_path):
                print(f"✓ Audio extracted: {os.path.basename(output_audio_path)}")
                return output_audio_path
            else:
                print(f"✗ Failed to extract audio: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None
    
    def remove_audio_from_video(self, video_path, output_video_path):
        """Remove audio from video using ffmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode != 0:
                print("FFmpeg not found, cannot remove audio")
                return None
            
            cmd = [
                'ffmpeg', '-i', video_path,
                '-c:v', 'copy',
                '-an',
                '-y',
                output_video_path
            ]
            
            print(f"Removing audio from: {os.path.basename(video_path)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_video_path):
                print(f"✓ Audio removed: {os.path.basename(output_video_path)}")
                return output_video_path
            else:
                print(f"✗ Failed to remove audio: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Error removing audio: {e}")
            return None
    
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
            
            num_frames = min(int(duration / interval_seconds) + 1, max_frames)
            if num_frames < 3:
                num_frames = 3
            
            frames = []
            for i in range(num_frames):
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
            print("Moondream2 model already loaded, reusing...")
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
            print("✓ Moondream2 model loaded successfully!\n")
            return self.moondream_tokenizer, self.moondream_model
            
        except Exception as e:
            print(f"Failed to load Moondream2 model: {e}")
            return None, None
    
    def load_llm_model(self, model_name):
        """Load the selected LLM model"""
        if model_name == "none":
            return None, None
        
        if self.llm_model is not None:
            print(f"LLM model already loaded, reusing...")
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
            
            self.llm_tokenizer = AutoTokenizer.from_pretrained(
                model_id,
                trust_remote_code=True
            )
            
            if self.llm_tokenizer.pad_token is None:
                self.llm_tokenizer.pad_token = self.llm_tokenizer.eos_token
            
            self.llm_model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
                trust_remote_code=True,
            )
            
            print(f"✓ LLM model {model_name} loaded successfully!\n")
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
        start_time = time.time()
        
        try:
            descriptions_text = "\n".join([
                f"At {time:.1f}s: {desc}"
                for time, desc in frame_descriptions
            ])
            
            prompt = f"""Write a FACTUAL description of this video scene based ONLY on these frame descriptions:

{descriptions_text}

RULES:
1. ONLY describe what is shown in the frames
2. DO NOT invent new characters, objects, or events
3. DO NOT add sounds, music, or audio descriptions
4. DO NOT assume narratives or stories
5. If something is not mentioned, DO NOT add it
6. Be precise and literal
7. Use ONLY English - no translations or other languages


Factual video description (English only):"""
            
            if self.debug_dir:
                self.save_debug_info(
                    "llm_prompt.txt",
                    prompt,
                    step="llm_prompt"
                )
            
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(self.device)
            
            input_length = inputs['input_ids'].shape[1]
            max_new_tokens = min(400, 4096 - input_length)
            
            if max_new_tokens < 100:
                raise ValueError("Prompt too long for model context")
            
            with torch.no_grad():
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
            
            full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            if prompt in full_response:
                response = full_response[len(prompt):].strip()
            else:
                response = full_response
            
            lines = response.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                conversational = ["Certainly", "Sure", "Here's", "Based on", "I think", "I believe", 
                                 "Let me", "Can you", "Also,", "To begin", "Alright,", "Well,"]
                skip_line = False
                for conv in conversational:
                    if line.lower().startswith(conv.lower()):
                        skip_line = True
                        break
                if not skip_line:
                    cleaned_lines.append(line)
            
            response = ' '.join(cleaned_lines).strip()
            
            if response and not response.endswith(('.', '!', '?')):
                last_period = response.rfind('.')
                if last_period > len(response) * 0.7:
                    response = response[:last_period + 1]
            
            end_time = time.time()
            generation_time = end_time - start_time
            
            print(f"  ⏱️  LLM caption generation took: {generation_time:.2f}s")
            
            if self.debug_dir:
                self.save_debug_info(
                    "llm_response.txt",
                    {
                        "original_response": full_response,
                        "cleaned_response": response,
                        "generation_time": generation_time,
                        "input_length": input_length,
                        "max_new_tokens": max_new_tokens
                    },
                    step="llm_response"
                )
            
            return response
            
        except Exception as e:
            end_time = time.time()
            generation_time = end_time - start_time
            print(f"  ⏱️  LLM generation failed after: {generation_time:.2f}s")
            print(f"LLM summarization failed: {e}")
            raise
    
    def apply_ltx_format(self, caption, format_type, use_qwen=True, scene_number=None):
        """Apply LTX format to the caption using Qwen model"""
        start_time = time.time()
        
        try:
            if not caption or caption == "No caption available":
                return caption
            
            if format_type == "Standard":
                system_msg = """You are a prompt restructuring expert. Restructure narrative prompts into organized paragraphs WITHOUT section headers.

Structure information in this order (no labels):
1. Main action/core scene
2. Movements and gestures  
3. Character appearances
4. Objects and equipment
5. Background and environment
6. Camera angles and movements
7. Lighting and colors
8. Changes or temporal events

Write as a single flowing paragraph with smooth transitions. Ensure proper punctuation with periods at the end of sentences and commas where appropriate.

CRITICAL INSTRUCTIONS:
- ONLY use English
- DO NOT provide translations in any other language
- DO NOT add comments like "Translation note:", "If you need English version", etc.
- ONLY describe what is visible in the scene
- DO NOT add sounds, audio descriptions, or anything not shown
- DO NOT invent new details
- Stay true to the original description
- DO NOT use conversational phrases like "Certainly", "Sure", "Here's", "Based on", "I think", "I believe"
- DO NOT address the user (no "Human:", "User:", etc.)
- Start directly with the description
- Output ONLY the restructured description with no additional text"""
            elif format_type == "T2V":
                system_msg = """You are an expert cinematic director. Write detailed, chronological descriptions of actions and scenes.

INCLUDE:
- Specific movements and gestures
- Character/object appearances precisely  
- Background and environment details
- Camera angles and movements
- Lighting and colors
- Any changes or sudden events

WRITE AS:
- A single flowing paragraph
- Start directly with the action
- Keep descriptions literal and precise
- Think like a cinematographer describing a shot list
- Do not change the user input intent, just enhance it
- Keep within 150 words

CRITICAL INSTRUCTIONS:
- ONLY use English
- DO NOT provide translations
- ONLY describe what is visible in the scene
- DO NOT add sounds, audio descriptions, or anything not shown
- DO NOT invent new details
- Stay true to the original description
- DO NOT use conversational phrases
- DO NOT address the user
- Output ONLY the enhanced prompt with no additional text"""
            elif format_type == "I2V":
                system_msg = """You are an expert cinematic director. Write detailed, chronological descriptions of actions and scenes.

PRIORITY:
1. Describe the image first
2. Then add any additional user input
3. If image caption contradicts user text, align to image caption

INCLUDE:
- Specific movements and gestures
- Character/object appearances precisely  
- Background and environment details
- Camera angles and movements
- Lighting and colors
- Any changes or sudden events

WRITE AS:
- A single flowing paragraph
- Start directly with the action
- Keep descriptions literal and precise
- Think like a cinematographer describing a shot list
- Keep within 250 words

CRITICAL INSTRUCTIONS:
- ONLY use English
- DO NOT provide translations
- DO NOT add comments or explanations
- ONLY describe what is visible in the scene
- DO NOT add sounds, audio descriptions, or anything not shown
- DO NOT invent new details
- Stay true to the original description
- DO NOT use conversational phrases
- DO NOT address the user
- Output ONLY the enhanced prompt with no additional text"""
            else:
                return caption
            
            if not use_qwen or self.llm_model is None or self.llm_tokenizer is None:
                print(f"Note: Cannot apply {format_type} format - LLM model not loaded")
                return caption
            
            prompt = f"""{system_msg}

ORIGINAL DESCRIPTION:
"{caption}"

RESTRUCTURED DESCRIPTION:"""
            
            print(f"Applying {format_type} LTX format to caption...")
            
            if self.debug_dir and scene_number is not None:
                self.save_debug_info(
                    f"ltx_{format_type.lower()}_prompt.txt",
                    prompt,
                    scene_number=scene_number,
                    step=f"ltx_{format_type.lower()}_prompt"
                )
            
            inputs = self.llm_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048).to(self.device)
            
            input_length = inputs['input_ids'].shape[1]
            max_new_tokens = min(500, 4096 - input_length)
            
            if max_new_tokens < 100:
                return caption
            
            with torch.no_grad():
                try:
                    outputs = self.llm_model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        temperature=0.1,
                        do_sample=False,
                        top_p=0.7,
                        repetition_penalty=1.2,
                        no_repeat_ngram_size=3,
                        pad_token_id=self.llm_tokenizer.pad_token_id,
                        eos_token_id=self.llm_tokenizer.eos_token_id,
                    )
                except AttributeError as e:
                    if "'DynamicCache' object has no attribute 'seen_tokens'" in str(e):
                        outputs = self.llm_model.generate(
                            input_ids=inputs['input_ids'],
                            attention_mask=inputs['attention_mask'],
                            max_new_tokens=max_new_tokens,
                            temperature=0.1,
                            do_sample=False,
                            top_p=0.7,
                            repetition_penalty=1.2,
                            no_repeat_ngram_size=3,
                            pad_token_id=self.llm_tokenizer.pad_token_id,
                            eos_token_id=self.llm_tokenizer.eos_token_id,
                        )
                    else:
                        raise
            
            full_response = self.llm_tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            if prompt in full_response:
                response = full_response[len(prompt):].strip()
            else:
                response = full_response
            
            response_lines = response.split('\n')
            cleaned_lines = []
            
            for line in response_lines:
                line = line.strip()
                if not line:
                    continue
                
                conversational_indicators = [
                    "Human:", "User:", "Assistant:", "AI:",
                    "Certainly!", "Sure!", "Here's", "Based on",
                    "I think", "I believe", "Let me", "Can you",
                    "Also,", "To begin", "Alright,", "Well,",
                    "So,", "Now,", "Then,", "Next,","Chinese translation:", "Chinese version:", "Translation:",
                "简中翻译:", "中文翻译:", "翻译:", "The rest was translated",
                "Translation note:", "If you need English version",
                "English Version:", "ENGLISH VERSION:", "(Translation note:",
                "Translation provided:", "Here's the translation:",
                "Translated to Chinese:", "中文:", "简体中文:", "繁体中文:",
                ]
                
                skip_line = False
                for indicator in conversational_indicators:
                    if line.lower().startswith(indicator.lower()):
                        skip_line = True
                        break
                
                if skip_line:
                    continue
                
                conversational_phrases = [
                    "add some details", "describe the sounds",
                    "heard in the scene", "in my opinion",
                    "from my perspective", "I would like to",
                    "I should mention", "I should note",
                ]
                
                has_conversational = False
                for phrase in conversational_phrases:
                    if phrase in line.lower():
                        has_conversational = True
                        break
                
                if has_conversational:
                    continue
                
                line = ' '.join(line.split())
                
                if line and line[0] in ['"', "'", '-', '*', '>']:
                    line = line[1:].strip()
                
                if line:
                    cleaned_lines.append(line)
            
            response = ' '.join(cleaned_lines).strip()
            
            if not response:
                sentences = re.split(r'[.!?]+', full_response)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if len(sentence) > 20:
                        is_conversational = False
                        for indicator in conversational_indicators:
                            if sentence.lower().startswith(indicator.lower()):
                                is_conversational = True
                                break
                        
                        if not is_conversational:
                            response = sentence + '.'
                            break
                
                if not response:
                    print(f"  ⚠️  Fallback failed, using original caption with cleaning")
                    response = caption
            
            response = response.strip()
            
            while True:
                orig_len = len(response)
                for pattern in ["Certainly, ", "Sure, ", "Okay, ", "Alright, ", "Well, ", "So, ", "Now, ", "Then, ", "Next, "]:
                    if response.lower().startswith(pattern.lower()):
                        response = response[len(pattern):].strip()
                        break
                
                if response and response[0] in ['"', "'"]:
                    response = response[1:].strip()
                if response and response[-1] in ['"', "'"]:
                    response = response[:-1].strip()
                
                if len(response) == orig_len:
                    break
            
            if response and not response.endswith(('.', '!', '?')):
                last_period = response.rfind('.')
                if last_period > len(response) * 0.7:
                    response = response[:last_period + 1]
                else:
                    response = response + '.'
            
            if format_type == "T2V" or format_type == "I2V":
                words = response.split()
                word_limit = 150 if format_type == "T2V" else 250
                if len(words) > word_limit:
                    response = ' '.join(words[:word_limit])
                    if not response.endswith('.'):
                        response += '.'
            
            conversational_check = [
                "Human:", "User:", "Assistant:", "AI:",
                "Can you add", "describe the sounds",
            ]
            
            for check in conversational_check:
                if check in response:
                    print(f"  ⚠️  Still found '{check}' after cleaning, removing...")
                    response = response.replace(check, "").strip()
            
            end_time = time.time()
            generation_time = end_time - start_time
            
            print(f"  ⏱️  LTX format generation took: {generation_time:.2f}s")
            
            if self.debug_dir and scene_number is not None:
                debug_data = {
                    "original_caption": caption,
                    "ltx_response": response,
                    "generation_time": generation_time,
                    "full_original_response": full_response,
                    "prompt_used": prompt,
                    "model_parameters": {
                        "temperature": 0.1,
                        "do_sample": False,
                        "top_p": 0.7,
                        "repetition_penalty": 1.2,
                        "no_repeat_ngram_size": 3
                    }
                }
                
                self.save_debug_info(
                    f"ltx_{format_type.lower()}_response.txt",
                    debug_data,
                    scene_number=scene_number,
                    step=f"ltx_{format_type.lower()}_response"
                )
            
            print(f"✓ Applied {format_type} format ({len(response.split())} words)")
            return response
            
        except Exception as e:
            end_time = time.time()
            generation_time = end_time - start_time
            print(f"  ⏱️  LTX format generation failed after: {generation_time:.2f}s")
            print(f"Error applying LTX format: {e}")
            
            if self.debug_dir and scene_number is not None:
                self.save_debug_info(
                    f"ltx_{format_type.lower()}_error.txt",
                    {
                        "error": str(e),
                        "generation_time": generation_time,
                        "original_caption": caption,
                        "format_type": format_type
                    },
                    scene_number=scene_number,
                    step=f"ltx_{format_type.lower()}_error"
                )
            
            return caption
    
    def smart_summarize(self, frame_descriptions, max_length=500):
        """Intelligent summarization without LLM"""
        try:
            if not frame_descriptions:
                return "No frames to describe."
            
            descriptions = [desc for _, desc in frame_descriptions]
            
            base_desc = max(descriptions, key=len)
            
            if len(frame_descriptions) > 1:
                first_desc = descriptions[0]
                last_desc = descriptions[-1]
                
                first_words = set(first_desc.lower().split()[:15])
                last_words = set(last_desc.lower().split()[:15])
                overlap = len(first_words.intersection(last_words)) / max(len(first_words), 1)
                
                if overlap < 0.6:
                    base_desc += " The scene evolves with changing compositions."
                else:
                    base_desc += " The scene remains consistent throughout."
            
            if len(base_desc) > max_length:
                for end_char in ['.', '!', '?']:
                    last_end = base_desc[:max_length].rfind(end_char)
                    if last_end > max_length * 0.7:
                        return base_desc[:last_end + 1]
                
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
        
        video_files.sort()
        return video_files
    
    def get_video_url_for_frontend(self, video_path):
        """Generate URL for video to be accessed by frontend"""
        try:
            abs_video_path = os.path.abspath(video_path)
            
            if not os.path.exists(abs_video_path):
                return None, f"File does not exist: {abs_video_path}"
            
            if not os.path.isfile(abs_video_path):
                return None, f"Path is not a file: {abs_video_path}"
            
            file_size = os.path.getsize(abs_video_path)
            
            encoded_path = urllib.parse.quote(abs_video_path, safe='')
            
            url = f"/video_scene/viewer/read_video?filepath={encoded_path}"
            
            return url, f"File exists: {abs_video_path} ({file_size:,} bytes)"
            
        except Exception as e:
            error_msg = f"Error generating video URL: {str(e)}"
            print(error_msg)
            
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
    
    def load_existing_captions(self, captions_dir, ltx_format, ltx_format_type):
        """Load existing caption files from directory"""
        scene_captions = []
        scene_captions_ltx = []
        
        if not os.path.exists(captions_dir):
            print(f"Captions directory not found: {captions_dir}")
            return [], []
        
        caption_files = []
        ltx_caption_files = []
        
        for filename in os.listdir(captions_dir):
            if filename.endswith('_caption.txt') and not filename.endswith('_ltx_'):
                caption_files.append(filename)
            elif filename.endswith('_caption_ltx_'):
                ltx_caption_files.append(filename)
        
        caption_files.sort()
        ltx_caption_files.sort()
        
        print(f"Found {len(caption_files)} caption files in {captions_dir}")
        
        # Parse scene numbers from filenames and map to 0-based indices
        caption_dict = {}
        ltx_caption_dict = {}
        
        for caption_file in caption_files:
            try:
                # Extract scene number from filename (e.g., "scene_0001_caption.txt" -> 1)
                match = re.search(r'scene_(\d+)_caption\.txt', caption_file)
                if match:
                    scene_number = int(match.group(1))  # Gets 1, 2, 3...
                    list_index = scene_number - 1  # Convert to 0-based for list
                    
                    filepath = os.path.join(captions_dir, caption_file)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    
                    caption_dict[list_index] = content
                    print(f"  ✓ Loaded: {caption_file} -> list index {list_index} ({len(content)} chars)")
            except Exception as e:
                print(f"  ✗ Failed to load {caption_file}: {e}")
        
        # Convert dictionary to sequential list
        if caption_dict:
            max_index = max(caption_dict.keys())
            scene_captions = [caption_dict.get(i, f"No caption for scene {i+1}") 
                             for i in range(max_index + 1)]
        
        if ltx_format:
            ltx_pattern = f"_ltx_{ltx_format_type.lower()}.txt"
            for ltx_file in ltx_caption_files:
                if ltx_pattern in ltx_file:
                    try:
                        match = re.search(r'scene_(\d+)_caption_ltx_', ltx_file)
                        if match:
                            scene_number = int(match.group(1))
                            list_index = scene_number - 1
                            
                            filepath = os.path.join(captions_dir, ltx_file)
                            with open(filepath, 'r', encoding='utf-8') as f:
                                content = f.read().strip()
                            
                            ltx_caption_dict[list_index] = content
                            print(f"  ✓ Loaded LTX: {ltx_file} -> list index {list_index} ({len(content)} chars)")
                    except Exception as e:
                        print(f"  ✗ Failed to load LTX {ltx_file}: {e}")
        
        if ltx_format and ltx_caption_dict:
            max_index = max(max(caption_dict.keys()) if caption_dict else 0, 
                           max(ltx_caption_dict.keys()) if ltx_caption_dict else 0)
            scene_captions_ltx = [ltx_caption_dict.get(i, "") 
                                 for i in range(max_index + 1)]
        
        if ltx_format and scene_captions and not scene_captions_ltx:
            scene_captions_ltx = scene_captions.copy()
            print(f"  ⚠️  No LTX files found, using regular captions for LTX output")
        
        return scene_captions, scene_captions_ltx
    
    def generate_captions(self, scene_video_paths, llm_model, sampling_interval,
                         max_frames, max_description_length, selected_scene_index,
                         use_cache, extract_assets, keep_models_loaded,
                         ltx_format, ltx_format_type, load_existing_files,
                         video_scenes_output_path=""):
        
        print(f"\n{'='*60}")
        print(f"🎬 VideoSceneCaption: Starting caption generation")
        print(f"Selected scene index: {selected_scene_index}")
        print(f"LLM model: {llm_model}")
        print(f"LTX format: {'Enabled' if ltx_format else 'Disabled'} ({ltx_format_type})")
        print(f"Load existing files: {'Enabled' if load_existing_files else 'Disabled'}")
        print(f"Extract assets: {extract_assets}")
        print(f"Keep models loaded: {keep_models_loaded}")
        print(f"Use cache: {use_cache}")
        print(f"{'='*60}")
        
        debug_info_lines = []
        debug_info_lines.append(f"VideoSceneCaption Debug Information")
        debug_info_lines.append(f"{'='*60}")
        debug_info_lines.append(f"Selected scene index: {selected_scene_index}")
        debug_info_lines.append(f"LTX format: {'Enabled' if ltx_format else 'Disabled'} ({ltx_format_type})")
        debug_info_lines.append(f"Load existing files: {'Enabled' if load_existing_files else 'Disabled'}")
        debug_info_lines.append(f"Extract assets: {extract_assets}")
        debug_info_lines.append(f"Keep models loaded: {keep_models_loaded}")
        debug_info_lines.append(f"Total input video paths: {len(scene_video_paths) if scene_video_paths else 0}")
        
        if video_scenes_output_path and os.path.exists(video_scenes_output_path):
            base_dir = video_scenes_output_path
            debug_info_lines.append(f"✓ Using VideoSceneExtractor output as base: {base_dir}")
            
            if not base_dir.endswith("scene_outputs"):
                base_dir = os.path.join(base_dir, "scene_outputs")
                debug_info_lines.append(f"  Adjusted to: {base_dir}")
        else:
            base_dir = folder_paths.get_output_directory()
            scene_outputs_dir = os.path.join(base_dir, "scene_outputs")
            base_dir = scene_outputs_dir
            debug_info_lines.append(f"Using default scene_outputs directory: {base_dir}")
        
        debug_dir = self.setup_debug_logging(base_dir)
        
        captions_dir = os.path.join(base_dir, "scene_captions")
        os.makedirs(captions_dir, exist_ok=True)
        debug_info_lines.append(f"Captions directory: {captions_dir}")
        debug_info_lines.append(f"Base directory: {base_dir}")
        
        selected_scene_video_path = ""
        selected_scene_audio_path = ""
        selected_scene_video_no_audio_path = ""
        
        if extract_assets:
            extracted_dir = os.path.join(base_dir, "extracted_assets")
            os.makedirs(extracted_dir, exist_ok=True)
            debug_info_lines.append(f"Extracted assets directory: {extracted_dir}")
        else:
            debug_info_lines.append(f"Asset extraction disabled")
        
        valid_video_paths = []
        if scene_video_paths and len(scene_video_paths) > 0:
            valid_video_paths = [p for p in scene_video_paths if p and os.path.exists(p)]
            debug_info_lines.append(f"Using {len(valid_video_paths)} provided video paths from LIST")
            
            for i, path in enumerate(valid_video_paths[:5]):
                abs_path = os.path.abspath(path)
                exists = os.path.exists(abs_path)
                debug_info_lines.append(f"  Video {i+1}: {abs_path} ({'Exists' if exists else 'MISSING'})")
            if len(valid_video_paths) > 5:
                debug_info_lines.append(f"  ... and {len(valid_video_paths) - 5} more")
        else:
            print("No video paths provided, searching for videos...")
            debug_info_lines.append("No video paths provided, searching for videos...")
            
            videos_dir = os.path.join(base_dir, "videos")
            if os.path.exists(videos_dir):
                valid_video_paths = self.find_video_files(videos_dir)
                debug_info_lines.append(f"Found {len(valid_video_paths)} videos in: {videos_dir}")
            else:
                valid_video_paths = self.find_video_files(base_dir)
                debug_info_lines.append(f"Found {len(valid_video_paths)} videos in: {base_dir}")
        
        if not valid_video_paths:
            debug_info_lines.append("ERROR: No valid video files found")
            print("Error: No valid video files found")
            return self.return_empty(captions_dir, selected_scene_index, extract_assets, ltx_format)
        
        debug_info_lines.append(f"Found {len(valid_video_paths)} valid video files")
        
        if load_existing_files:
            print(f"\n📂 LOADING EXISTING FILES MODE")
            print(f"  Looking for existing caption files in: {captions_dir}")
            
            scene_captions, scene_captions_ltx = self.load_existing_captions(captions_dir, ltx_format, ltx_format_type)
            
            if scene_captions:
                print(f"  ✓ Successfully loaded {len(scene_captions)} existing captions")
                debug_info_lines.append(f"\nLoaded {len(scene_captions)} existing caption files")
                
                metadata = {
                    "base_directory": base_dir,
                    "captions_directory": captions_dir,
                    "llm_model": llm_model,
                    "sampling_interval": sampling_interval,
                    "max_frames": max_frames,
                    "max_description_length": max_description_length,
                    "extract_assets": extract_assets,
                    "ltx_format": ltx_format,
                    "ltx_format_type": ltx_format_type,
                    "load_existing_files": True,
                    "total_scenes": len(scene_captions),
                    "scenes": []
                }
                
                scene_video_urls = []
                for i, video_path in enumerate(valid_video_paths[:len(scene_captions)]):
                    video_url, _ = self.get_video_url_for_frontend(video_path)
                    scene_video_urls.append(video_url)
                    
                    scene_metadata = {
                        "index": i,
                        "scene_number": i + 1,  # 1-based scene number
                        "video_path": video_path if i < len(valid_video_paths) else "",
                        "video_filename": os.path.basename(video_path) if i < len(valid_video_paths) else f"scene_{(i+1):04d}",
                        "video_url": video_url,
                        "caption": scene_captions[i] if i < len(scene_captions) else "",
                        "caption_ltx": scene_captions_ltx[i] if i < len(scene_captions_ltx) else "",
                        "loaded_from_file": True
                    }
                    metadata["scenes"].append(scene_metadata)
                
                if extract_assets:
                    internal_index = selected_scene_index - 1
                    if 0 <= internal_index < len(valid_video_paths):
                        video_path = valid_video_paths[internal_index]
                        
                        print(f"\n📦 Extracting assets for selected scene {selected_scene_index}...")
                        debug_info_lines.append(f"\nExtracting assets for selected scene {selected_scene_index}...")
                        
                        extracted_dir = os.path.join(base_dir, "extracted_assets")
                        os.makedirs(extracted_dir, exist_ok=True)
                        
                        selected_scene_video_path = os.path.join(extracted_dir, f"scene_{(internal_index+1):04d}_video.mp4")
                        try:
                            shutil.copy2(video_path, selected_scene_video_path)
                            print(f"  ✓ Video copied: {os.path.basename(selected_scene_video_path)}")
                            debug_info_lines.append(f"  ✓ Copied video to: {os.path.basename(selected_scene_video_path)}")
                        except Exception as e:
                            print(f"  ✗ Failed to copy video: {e}")
                            debug_info_lines.append(f"  ✗ Failed to copy video: {e}")
                            selected_scene_video_path = video_path
                        
                        audio_filename = f"scene_{(internal_index+1):04d}_audio.mp3"
                        selected_scene_audio_path = os.path.join(extracted_dir, audio_filename)
                        audio_path = self.extract_audio_from_video(video_path, selected_scene_audio_path)
                        if audio_path:
                            debug_info_lines.append(f"  ✓ Extracted audio: {os.path.basename(audio_path)}")
                            selected_scene_audio_path = audio_path
                        else:
                            debug_info_lines.append(f"  ✗ Failed to extract audio")
                            selected_scene_audio_path = ""
                        
                        video_no_audio_filename = f"scene_{(internal_index+1):04d}_video_no_audio.mp4"
                        selected_scene_video_no_audio_path = os.path.join(extracted_dir, video_no_audio_filename)
                        video_no_audio_path = self.remove_audio_from_video(video_path, selected_scene_video_no_audio_path)
                        if video_no_audio_path:
                            debug_info_lines.append(f"  ✓ Created video without audio: {os.path.basename(video_no_audio_path)}")
                            selected_scene_video_no_audio_path = video_no_audio_path
                        else:
                            debug_info_lines.append(f"  ✗ Failed to create video without audio")
                            selected_scene_video_no_audio_path = ""
                
                internal_index = selected_scene_index - 1
                selected_caption = ""
                selected_caption_ltx = ""
                
                if 0 <= internal_index < len(scene_captions):
                    selected_caption = scene_captions[internal_index]
                    selected_caption_ltx = scene_captions_ltx[internal_index] if internal_index < len(scene_captions_ltx) else selected_caption
                    
                    if ltx_format and selected_caption_ltx and selected_caption_ltx != selected_caption:
                        selected_caption = selected_caption_ltx
                        debug_info_lines.append(f"✓ Using LTX formatted caption as primary output")
                elif scene_captions:
                    selected_caption = scene_captions[0]
                    selected_caption_ltx = scene_captions_ltx[0] if scene_captions_ltx else selected_caption
                    internal_index = 0
                    if ltx_format and selected_caption_ltx and selected_caption_ltx != selected_caption:
                        selected_caption = selected_caption_ltx
                        debug_info_lines.append(f"✓ Using LTX formatted caption as primary output")
                
                debug_info_lines.append(f"\n{'='*60}")
                debug_info_lines.append(f"✓ Complete! Loaded {len(scene_captions)} existing captions")
                if ltx_format:
                    debug_info_lines.append(f"  Loaded {len(scene_captions_ltx)} LTX formatted captions ({ltx_format_type})")
                debug_info_lines.append(f"  Output directory: {captions_dir}")
                debug_info_lines.append(f"  Selected scene: {selected_scene_index} (internal: {internal_index})")
                debug_info_lines.append(f"  Selected caption length: {len(selected_caption)} characters")
                if ltx_format:
                    debug_info_lines.append(f"  Selected LTX caption length: {len(selected_caption_ltx)} characters")
                
                debug_info = "\n".join(debug_info_lines)
                
                print(f"\n{'='*60}")
                print(f"✓ Complete! Loaded {len(scene_captions)} existing captions")
                if ltx_format:
                    print(f"  Loaded {len(scene_captions_ltx)} LTX formatted captions ({ltx_format_type})")
                print(f"  Base directory: {base_dir}")
                print(f"  Captions directory: {captions_dir}")
                print(f"  Selected scene: {selected_scene_index}")
                print(f"  LTX format: {'Enabled' if ltx_format else 'Disabled'} ({ltx_format_type if ltx_format else 'N/A'})")
                print(f"  Load existing files: Enabled")
                print(f"  Asset extraction: {'Enabled' if extract_assets else 'Disabled'}")
                print(f"{'='*60}")
                
                return {
                    "ui": {
                        "text": [selected_caption],
                        "scene_captions": [scene_captions],
                        "scene_video_paths": [valid_video_paths[:len(scene_captions)]],
                        "scene_video_urls": [scene_video_urls],
                        "total_scenes": [len(scene_captions)],
                        "selected_index": [selected_scene_index],
                        "captions_dir": [captions_dir],
                        "base_dir": [base_dir],
                        "debug_info": [debug_info],
                        "selected_scene_video": [selected_scene_video_path],
                        "selected_scene_audio": [selected_scene_audio_path],
                        "selected_scene_video_no_audio": [selected_scene_video_no_audio_path],
                        "selected_caption_ltx": [selected_caption_ltx],
                    },
                    "result": (
                        captions_dir, 
                        scene_captions, 
                        json.dumps(metadata, indent=2), 
                        selected_caption,
                        debug_info,
                        selected_scene_video_path,
                        selected_scene_audio_path,
                        selected_scene_video_no_audio_path,
                        selected_caption_ltx
                    )
                }
            else:
                print(f"  ⚠️  No existing caption files found, falling back to normal processing")
                debug_info_lines.append(f"\nNo existing caption files found, falling back to normal processing")
        
        cache_key_params = f"{len(valid_video_paths)}_{llm_model}_{sampling_interval}_{max_frames}_{max_description_length}_{base_dir}_{extract_assets}_{ltx_format}_{ltx_format_type}"
        cache_key = hashlib.md5(cache_key_params.encode()).hexdigest()[:16]
        
        cache_file = os.path.join(captions_dir, f"cache_{cache_key}.json")
        
        scene_captions = []
        scene_captions_ltx = []
        metadata = {
            "base_directory": base_dir,
            "captions_directory": captions_dir,
            "llm_model": llm_model,
            "sampling_interval": sampling_interval,
            "max_frames": max_frames,
            "max_description_length": max_description_length,
            "extract_assets": extract_assets,
            "ltx_format": ltx_format,
            "ltx_format_type": ltx_format_type,
            "load_existing_files": load_existing_files,
            "total_scenes": len(valid_video_paths),
            "scenes": []
        }
        
        if extract_assets:
            metadata["extracted_assets_directory"] = os.path.join(base_dir, "extracted_assets")
        
        video_paths_changed = self.last_video_paths != valid_video_paths
        cache_valid = False
        
        if use_cache and os.path.exists(cache_file) and not video_paths_changed and not load_existing_files:
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                scene_captions = cached_data.get("scene_captions", [])
                scene_captions_ltx = cached_data.get("scene_captions_ltx", [])
                metadata = cached_data.get("metadata", metadata)
                
                if len(scene_captions) == len(valid_video_paths):
                    cache_valid = True
                    print(f"\n✓ CACHE HIT: Loaded {len(scene_captions)} cached captions")
                    print(f"  Cache file: {cache_file}")
                    print(f"  Skipping video processing...\n")
                    debug_info_lines.append(f"✓ Loaded {len(scene_captions)} cached captions")
                    if ltx_format:
                        debug_info_lines.append(f"✓ Loaded {len(scene_captions_ltx)} LTX formatted captions")
                else:
                    debug_info_lines.append(f"Cache invalid: expected {len(valid_video_paths)} captions, got {len(scene_captions)}")
                    scene_captions = []
                    scene_captions_ltx = []
            except Exception as e:
                debug_info_lines.append(f"Error loading cache: {e}")
        
        self.last_video_paths = valid_video_paths
        self.last_index = selected_scene_index
        
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
                
                video_url, url_debug = self.get_video_url_for_frontend(video_path)
                scene_video_urls.append(video_url)
                
                if video_url:
                    debug_info_lines.append(f"  ✓ URL generated: {video_url}")
                else:
                    debug_info_lines.append(f"  ✗ URL generation failed")
                
                debug_info_lines.append(f"  Debug: {url_debug}")
                
                video_debug_info.append({
                    "scene_number": i + 1,  # 1-based scene number
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
                    "scene_number": i + 1,
                    "input_path": video_path,
                    "absolute_path": abs_video_path,
                    "exists": False,
                    "file_size": 0,
                    "url": None,
                    "debug": "File does not exist"
                })
        
        successful_urls = sum(1 for url in scene_video_urls if url)
        debug_info_lines.append(f"\nURL Generation Summary:")
        debug_info_lines.append(f"  Total videos: {len(valid_video_paths)}")
        debug_info_lines.append(f"  Successful URLs: {successful_urls}")
        debug_info_lines.append(f"  Failed URLs: {len(valid_video_paths) - successful_urls}")
        
        if not cache_valid and not load_existing_files:
            print(f"\n{'='*60}")
            print(f"🔄 CACHE MISS: Processing {len(valid_video_paths)} videos...")
            print(f"{'='*60}\n")
            
            debug_info_lines.append(f"\nLoading Moondream2 model...")
            moondream_tokenizer, moondream_model = self.load_moondream_model()
            if not moondream_model:
                debug_info_lines.append(f"Failed to load Moondream2 model")
                print("Failed to load Moondream2 model")
                return self.return_empty(captions_dir, selected_scene_index, extract_assets, ltx_format)
            
            llm_tokenizer = None
            llm_model_obj = None
            use_llm = llm_model != "none"
            
            if use_llm:
                debug_info_lines.append(f"Loading LLM model: {llm_model}...")
                llm_tokenizer, llm_model_obj = self.load_llm_model(llm_model)
                if not llm_model_obj:
                    debug_info_lines.append("LLM model not available, using smart summarization")
                    use_llm = False
            
            scene_captions = []
            scene_captions_ltx = []
            metadata["scenes"] = []
            
            total_videos = len(valid_video_paths)
            self.create_progress_bar(total_videos, "Generating captions")
            
            for i, video_path in enumerate(valid_video_paths):
                scene_number = i + 1  # 1-based scene number
                video_filename = os.path.basename(video_path)
                
                print(f"\n{'─'*60}")
                print(f"🎬 Processing Scene {scene_number}/{total_videos}: {video_filename}")
                print(f"{'─'*60}")
                
                debug_info_lines.append(f"\nProcessing scene {scene_number}/{total_videos}: {video_filename}")
                
                self.update_progress(i + 1, total_videos, f"Scene {scene_number}/{total_videos}")
                
                duration = self.get_video_duration(video_path)
                print(f"  Duration: {duration:.2f}s")
                debug_info_lines.append(f"  Duration: {duration:.2f}s")
                
                print(f"  Extracting keyframes (max {max_frames}, interval {sampling_interval}s)...")
                frames = self.extract_keyframes(video_path, sampling_interval, max_frames)
                print(f"  ✓ Extracted {len(frames)} keyframes")
                debug_info_lines.append(f"  Extracted {len(frames)} keyframes")
                
                if self.debug_dir:
                    self.save_debug_info(
                        "frame_extraction.json",
                        {
                            "video_path": video_path,
                            "duration": duration,
                            "frames_extracted": len(frames),
                            "sampling_interval": sampling_interval,
                            "max_frames": max_frames
                        },
                        scene_number=scene_number,
                        step="frame_extraction"
                    )
                
                if not frames:
                    caption = "No frames extracted from video."
                    scene_captions.append(caption)
                    scene_captions_ltx.append(caption)
                    metadata["scenes"].append({
                        "index": i,
                        "scene_number": scene_number,
                        "video_path": video_path,
                        "video_filename": video_filename,
                        "video_url": scene_video_urls[i] if i < len(scene_video_urls) else None,
                        "duration": duration,
                        "keyframes": 0,
                        "caption": caption,
                        "caption_ltx": caption,
                        "method": "error"
                    })
                    print(f"  ✗ Failed to extract frames")
                    debug_info_lines.append(f"  ✗ Failed to extract frames")
                    continue
                
                print(f"  Analyzing frames with Moondream2...")
                frame_descriptions = []
                frame_times = []
                
                for frame_idx, (timestamp, frame_image) in enumerate(frames):
                    frame_start_time = time.time()
                    print(f"    Frame {frame_idx+1}/{len(frames)} at {timestamp:.1f}s...", end=" ")
                    description = self.describe_frame(frame_image, moondream_tokenizer, moondream_model)
                    frame_end_time = time.time()
                    frame_time = frame_end_time - frame_start_time
                    
                    frame_descriptions.append((timestamp, description))
                    frame_times.append(frame_time)
                    
                    print(f"✓ ({len(description)} chars, {frame_time:.2f}s)")
                    debug_info_lines.append(f"    Frame {frame_idx+1}/{len(frames)} at {timestamp:.1f}s: {len(description)} chars, {frame_time:.2f}s")
                
                if self.debug_dir:
                    self.save_debug_info(
                        "frame_descriptions.json",
                        {
                            "frame_descriptions": [
                                {
                                    "timestamp": ts,
                                    "description": desc[:500] + "..." if len(desc) > 500 else desc,
                                    "length": len(desc)
                                }
                                for ts, desc in frame_descriptions
                            ],
                            "total_frames": len(frames),
                            "total_description_chars": sum(len(desc) for _, desc in frame_descriptions),
                            "average_frame_time": sum(frame_times) / len(frame_times) if frame_times else 0
                        },
                        scene_number=scene_number,
                        step="frame_descriptions"
                    )
                
                video_caption = ""
                method_used = ""
                llm_generation_time = 0
                
                if use_llm and llm_model_obj and len(frame_descriptions) > 1:
                    try:
                        print(f"  💭 Generating caption with {llm_model}...")
                        debug_info_lines.append(f"  Generating caption with {llm_model}...")
                        
                        llm_start_time = time.time()
                        video_caption = self.summarize_with_llm(
                            frame_descriptions, 
                            llm_tokenizer, 
                            llm_model_obj,
                            max_length=max_description_length
                        )
                        llm_end_time = time.time()
                        llm_generation_time = llm_end_time - llm_start_time
                        
                        method_used = f"llm_{llm_model}"
                        print(f"  ✓ Caption generated ({len(video_caption)} chars, {llm_generation_time:.2f}s)")
                        debug_info_lines.append(f"  ✓ Caption generated ({len(video_caption)} chars, {llm_generation_time:.2f}s)")
                    except Exception as e:
                        print(f"  ✗ LLM failed: {e}")
                        print(f"  Falling back to smart summarization...")
                        debug_info_lines.append(f"  LLM failed: {e}")
                        debug_info_lines.append("  Falling back to smart summarization...")
                        video_caption = self.smart_summarize(frame_descriptions, max_description_length)
                        method_used = "smart_fallback"
                else:
                    print(f"  📝 Using smart summarization...")
                    debug_info_lines.append(f"  Using smart summarization...")
                    video_caption = self.smart_summarize(frame_descriptions, max_description_length)
                    method_used = "smart" if llm_model == "none" else "smart_fallback"
                    print(f"  ✓ Caption generated ({len(video_caption)} chars)")
                
                video_caption = video_caption.strip()
                if len(video_caption) > max_description_length:
                    video_caption = video_caption[:max_description_length].rsplit(' ', 1)[0] + "..."
                
                video_caption_ltx = video_caption
                ltx_generation_time = 0
                
                if ltx_format and use_llm and llm_model_obj:
                    try:
                        print(f"  🎨 Applying {ltx_format_type} LTX format...")
                        debug_info_lines.append(f"  Applying {ltx_format_type} LTX format...")
                        
                        if llm_model != "qwen2.5-7b" and ltx_format:
                            print(f"  ⚠️  Note: LTX format works best with Qwen model")
                        
                        ltx_start_time = time.time()
                        video_caption_ltx = self.apply_ltx_format(
                            video_caption, 
                            ltx_format_type,
                            use_qwen=(llm_model_obj is not None),
                            scene_number=scene_number
                        )
                        ltx_end_time = time.time()
                        ltx_generation_time = ltx_end_time - ltx_start_time
                        
                        if video_caption_ltx != video_caption:
                            print(f"    ✓ LTX format applied ({len(video_caption_ltx.split())} words, {ltx_generation_time:.2f}s)")
                            debug_info_lines.append(f"    ✓ LTX format applied: {len(video_caption_ltx.split())} words, {ltx_generation_time:.2f}s")
                        else:
                            print(f"    ⚠️  LTX format unchanged (using original)")
                            debug_info_lines.append(f"    ⚠️  LTX format unchanged")
                    except Exception as e:
                        print(f"    ✗ LTX format error: {e}")
                        debug_info_lines.append(f"    ✗ LTX format error: {e}")
                        video_caption_ltx = video_caption
                
                scene_captions.append(video_caption)
                scene_captions_ltx.append(video_caption_ltx)
                
                # ✅ UPDATED: Now uses scene_number (1-based) for filenames
                caption_filename = f"scene_{scene_number:04d}_caption.txt"
                caption_filepath = os.path.join(captions_dir, caption_filename)
                with open(caption_filepath, 'w', encoding='utf-8') as f:
                    f.write(video_caption + '\n')
                
                print(f"  ✓ Caption saved: {caption_filename}")
                
                if video_caption_ltx != video_caption:
                    # ✅ UPDATED: Now uses scene_number (1-based) for LTX filenames
                    caption_ltx_filename = f"scene_{scene_number:04d}_caption_ltx_{ltx_format_type.lower()}.txt"
                    caption_ltx_filepath = os.path.join(captions_dir, caption_ltx_filename)
                    with open(caption_ltx_filepath, 'w', encoding='utf-8') as f:
                        f.write(video_caption_ltx + '\n')
                    print(f"  ✓ LTX caption saved: {caption_ltx_filename}")
                
                if self.debug_dir:
                    self.save_debug_info(
                        "timing_summary.json",
                        {
                            "scene_number": scene_number,
                            "video_filename": video_filename,
                            "duration": duration,
                            "frames_extracted": len(frames),
                            "frame_description_time_total": sum(frame_times),
                            "frame_description_time_avg": sum(frame_times) / len(frame_times) if frame_times else 0,
                            "llm_generation_time": llm_generation_time,
                            "ltx_generation_time": ltx_generation_time,
                            "total_processing_time": sum(frame_times) + llm_generation_time + ltx_generation_time,
                            "caption_length": len(video_caption),
                            "ltx_caption_length": len(video_caption_ltx),
                            "method_used": method_used
                        },
                        scene_number=scene_number,
                        step="timing_summary"
                    )
                
                is_selected_scene = (scene_number == selected_scene_index)
                
                if extract_assets and is_selected_scene:
                    print(f"  📦 Extracting assets for selected scene...")
                    debug_info_lines.append(f"  This is the selected scene (number {selected_scene_index}) - extracting assets...")
                    
                    extracted_dir = os.path.join(base_dir, "extracted_assets")
                    os.makedirs(extracted_dir, exist_ok=True)
                    
                    # ✅ UPDATED: Now uses scene_number (1-based) for extracted asset filenames
                    selected_scene_video_path = os.path.join(extracted_dir, f"scene_{scene_number:04d}_video.mp4")
                    try:
                        shutil.copy2(video_path, selected_scene_video_path)
                        print(f"    ✓ Video copied: {os.path.basename(selected_scene_video_path)}")
                        debug_info_lines.append(f"    ✓ Copied video to: {os.path.basename(selected_scene_video_path)}")
                    except Exception as e:
                        print(f"    ✗ Failed to copy video: {e}")
                        debug_info_lines.append(f"    ✗ Failed to copy video: {e}")
                        selected_scene_video_path = video_path
                    
                    audio_filename = f"scene_{scene_number:04d}_audio.mp3"
                    selected_scene_audio_path = os.path.join(extracted_dir, audio_filename)
                    audio_path = self.extract_audio_from_video(video_path, selected_scene_audio_path)
                    if audio_path:
                        debug_info_lines.append(f"    ✓ Extracted audio: {os.path.basename(audio_path)}")
                        selected_scene_audio_path = audio_path
                    else:
                        debug_info_lines.append(f"    ✗ Failed to extract audio")
                        selected_scene_audio_path = ""
                    
                    video_no_audio_filename = f"scene_{scene_number:04d}_video_no_audio.mp4"
                    selected_scene_video_no_audio_path = os.path.join(extracted_dir, video_no_audio_filename)
                    video_no_audio_path = self.remove_audio_from_video(video_path, selected_scene_video_no_audio_path)
                    if video_no_audio_path:
                        debug_info_lines.append(f"    ✓ Created video without audio: {os.path.basename(video_no_audio_path)}")
                        selected_scene_video_no_audio_path = video_no_audio_path
                    else:
                        debug_info_lines.append(f"    ✗ Failed to create video without audio")
                        selected_scene_video_no_audio_path = ""
                
                scene_metadata = {
                    "index": i,
                    "scene_number": scene_number,
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
                    "caption_ltx": video_caption_ltx,
                    "caption_file": caption_filename,
                    "caption_filepath": caption_filepath,
                    "method": method_used,
                    "is_selected_scene": is_selected_scene,
                    "ltx_format_applied": ltx_format,
                    "ltx_format_type": ltx_format_type if ltx_format else None,
                    "timing": {
                        "frame_description_total": sum(frame_times),
                        "llm_generation": llm_generation_time,
                        "ltx_generation": ltx_generation_time,
                        "total_processing": sum(frame_times) + llm_generation_time + ltx_generation_time
                    }
                }
                
                if video_caption_ltx != video_caption:
                    caption_ltx_filename = f"scene_{scene_number:04d}_caption_ltx_{ltx_format_type.lower()}.txt"
                    caption_ltx_filepath = os.path.join(captions_dir, caption_ltx_filename)
                    scene_metadata["caption_ltx_file"] = caption_ltx_filename
                    scene_metadata["caption_ltx_filepath"] = caption_ltx_filepath
                
                if extract_assets and is_selected_scene:
                    scene_metadata["extracted_assets"] = {
                        "video_path": selected_scene_video_path,
                        "audio_path": selected_scene_audio_path,
                        "video_no_audio_path": selected_scene_video_no_audio_path
                    }
                
                metadata["scenes"].append(scene_metadata)
                debug_info_lines.append(f"  ✓ Scene {scene_number} complete")
            
            if use_cache:
                cache_data = {
                    "scene_captions": scene_captions,
                    "scene_captions_ltx": scene_captions_ltx,
                    "metadata": metadata,
                    "cache_key": cache_key
                }
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                print(f"\n✓ Results cached: {cache_file}")
                debug_info_lines.append(f"\n✓ Results cached: {cache_file}")
            
            if keep_models_loaded:
                print("\n✓ Keeping models loaded for future use...")
                debug_info_lines.append("\nKeeping models loaded for future use...")
            else:
                print("\n🗑️ Unloading models...")
                debug_info_lines.append("\nUnloading models...")
                if moondream_model:
                    del moondream_model
                    self.moondream_model = None
                    self.moondream_tokenizer = None
                
                if llm_model_obj:
                    del llm_model_obj
                    self.llm_model = None
                    self.llm_tokenizer = None
                
                torch.cuda.empty_cache()
                print("✓ Models unloaded and GPU memory cleared")
                debug_info_lines.append("Models unloaded and GPU memory cleared")
        
        else:
            debug_info_lines.append(f"\n{'='*60}")
            debug_info_lines.append(f"✓ Using cached captions - skipping video processing")
            debug_info_lines.append(f"  Cached scenes: {len(scene_captions)}")
            debug_info_lines.append(f"  Cached LTX scenes: {len(scene_captions_ltx)}")
            debug_info_lines.append(f"  Cache file: {cache_file}")
            debug_info_lines.append(f"{'='*60}")
            
            if extract_assets:
                internal_index = selected_scene_index - 1
                if 0 <= internal_index < len(valid_video_paths):
                    video_path = valid_video_paths[internal_index]
                    
                    print(f"\n📦 Extracting assets for selected scene {selected_scene_index}...")
                    debug_info_lines.append(f"\nExtracting assets for selected scene {selected_scene_index}...")
                    
                    extracted_dir = os.path.join(base_dir, "extracted_assets")
                    os.makedirs(extracted_dir, exist_ok=True)
                    
                    # ✅ UPDATED: Now uses selected_scene_index (1-based) for extracted asset filenames
                    selected_scene_video_path = os.path.join(extracted_dir, f"scene_{selected_scene_index:04d}_video.mp4")
                    try:
                        shutil.copy2(video_path, selected_scene_video_path)
                        print(f"  ✓ Video copied: {os.path.basename(selected_scene_video_path)}")
                        debug_info_lines.append(f"  ✓ Copied video to: {os.path.basename(selected_scene_video_path)}")
                    except Exception as e:
                        print(f"  ✗ Failed to copy video: {e}")
                        debug_info_lines.append(f"  ✗ Failed to copy video: {e}")
                        selected_scene_video_path = video_path
                    
                    audio_filename = f"scene_{selected_scene_index:04d}_audio.mp3"
                    selected_scene_audio_path = os.path.join(extracted_dir, audio_filename)
                    audio_path = self.extract_audio_from_video(video_path, selected_scene_audio_path)
                    if audio_path:
                        debug_info_lines.append(f"  ✓ Extracted audio: {os.path.basename(audio_path)}")
                        selected_scene_audio_path = audio_path
                    else:
                        debug_info_lines.append(f"  ✗ Failed to extract audio")
                        selected_scene_audio_path = ""
                    
                    video_no_audio_filename = f"scene_{selected_scene_index:04d}_video_no_audio.mp4"
                    selected_scene_video_no_audio_path = os.path.join(extracted_dir, video_no_audio_filename)
                    video_no_audio_path = self.remove_audio_from_video(video_path, selected_scene_video_no_audio_path)
                    if video_no_audio_path:
                        debug_info_lines.append(f"  ✓ Created video without audio: {os.path.basename(video_no_audio_path)}")
                        selected_scene_video_no_audio_path = video_no_audio_path
                    else:
                        debug_info_lines.append(f"  ✗ Failed to create video without audio")
                        selected_scene_video_no_audio_path = ""
        
        metadata_path = os.path.join(captions_dir, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        debug_info_lines.append(f"\nMetadata saved: {metadata_path}")
        
        internal_index = selected_scene_index - 1
        selected_caption = ""
        selected_caption_ltx = ""
        
        if 0 <= internal_index < len(scene_captions):
            selected_caption = scene_captions[internal_index]
            selected_caption_ltx = scene_captions_ltx[internal_index] if internal_index < len(scene_captions_ltx) else selected_caption
            
            if ltx_format and selected_caption_ltx and selected_caption_ltx != selected_caption:
                print(f"✓ Using LTX formatted caption as primary output")
                debug_info_lines.append(f"✓ Using LTX formatted caption as primary output")
                selected_caption = selected_caption_ltx
            
            debug_info_lines.append(f"\nSelected caption (scene {selected_scene_index}):")
            debug_info_lines.append(f"  {selected_caption[:200]}...")
            
            if ltx_format and selected_caption_ltx != selected_caption:
                debug_info_lines.append(f"\nOriginal LTX caption ({ltx_format_type}):")
                debug_info_lines.append(f"  {selected_caption_ltx[:200]}...")
        elif scene_captions:
            selected_caption = scene_captions[0]
            selected_caption_ltx = scene_captions_ltx[0] if scene_captions_ltx else selected_caption
            internal_index = 0
            
            if ltx_format and selected_caption_ltx and selected_caption_ltx != selected_caption:
                print(f"✓ Using LTX formatted caption as primary output")
                debug_info_lines.append(f"✓ Using LTX formatted caption as primary output")
                selected_caption = selected_caption_ltx
            
            debug_info_lines.append(f"\nSelected index out of bounds, using first caption")
        
        if extract_assets:
            debug_info_lines.append(f"\nExtracted Assets for Selected Scene:")
            debug_info_lines.append(f"  Original video: {selected_scene_video_path if selected_scene_video_path else 'Not available'}")
            debug_info_lines.append(f"  Audio only: {selected_scene_audio_path if selected_scene_audio_path else 'Not available'}")
            debug_info_lines.append(f"  Video without audio: {selected_scene_video_no_audio_path if selected_scene_video_no_audio_path else 'Not available'}")
        else:
            debug_info_lines.append(f"\nAsset extraction disabled - no assets extracted")
        
        debug_info_lines.append(f"\n{'='*60}")
        debug_info_lines.append(f"✓ Complete! Generated {len(scene_captions)} scene captions")
        if ltx_format:
            debug_info_lines.append(f"  Generated {len(scene_captions_ltx)} LTX formatted captions ({ltx_format_type})")
        debug_info_lines.append(f"  Output directory: {captions_dir}")
        debug_info_lines.append(f"  Selected scene: {selected_scene_index} (internal: {internal_index})")
        debug_info_lines.append(f"  Selected caption length: {len(selected_caption)} characters")
        if ltx_format:
            debug_info_lines.append(f"  Selected LTX caption length: {len(selected_caption_ltx)} characters")
        debug_info_lines.append(f"  Video URLs generated: {len([url for url in scene_video_urls if url])}/{len(valid_video_paths)}")
        debug_info_lines.append(f"  Base directory: {base_dir}")
        debug_info_lines.append(f"  Captions saved in: {captions_dir}")
        
        debug_info = "\n".join(debug_info_lines)
        
        print(f"\n{'='*60}")
        print(f"✓ Complete! Generated {len(scene_captions)} scene captions")
        if ltx_format:
            print(f"  Generated {len(scene_captions_ltx)} LTX formatted captions ({ltx_format_type})")
        print(f"  Base directory: {base_dir}")
        print(f"  Captions directory: {captions_dir}")
        print(f"  Selected scene: {selected_scene_index}")
        print(f"  LTX format: {'Enabled' if ltx_format else 'Disabled'} ({ltx_format_type if ltx_format else 'N/A'})")
        print(f"  Load existing files: {'Enabled' if load_existing_files else 'Disabled'}")
        print(f"  Asset extraction: {'Enabled' if extract_assets else 'Disabled'}")
        print(f"  Video URLs generated: {len([url for url in scene_video_urls if url])}/{len(valid_video_paths)}")
        print(f"  Models kept loaded: {keep_models_loaded}")
        print(f"  Debug logs saved to: {debug_dir}")
        print(f"{'='*60}")
        
        return {
            "ui": {
                "text": [selected_caption],
                "scene_captions": [scene_captions],
                "scene_video_paths": [valid_video_paths],
                "scene_video_urls": [scene_video_urls],
                "total_scenes": [len(scene_captions)],
                "selected_index": [selected_scene_index],
                "captions_dir": [captions_dir],
                "base_dir": [base_dir],
                "debug_info": [debug_info],
                "selected_scene_video": [selected_scene_video_path],
                "selected_scene_audio": [selected_scene_audio_path],
                "selected_scene_video_no_audio": [selected_scene_video_no_audio_path],
                "selected_caption_ltx": [selected_caption_ltx],
            },
            "result": (
                captions_dir, 
                scene_captions, 
                json.dumps(metadata, indent=2), 
                selected_caption,
                debug_info,
                selected_scene_video_path,
                selected_scene_audio_path,
                selected_scene_video_no_audio_path,
                selected_caption_ltx
            )
        }
    
    def return_empty(self, output_dir, selected_scene_index, extract_assets, ltx_format):
        """Return empty results"""
        debug_info = f"No video files found to process.\nOutput directory: {output_dir}\nSelected scene index: {selected_scene_index}\nAsset extraction: {'Enabled' if extract_assets else 'Disabled'}\nLTX format: {'Enabled' if ltx_format else 'Disabled'}"
        
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
                "selected_scene_video": [""],
                "selected_scene_audio": [""],
                "selected_scene_video_no_audio": [""],
                "selected_caption_ltx": [""],
            },
            "result": (output_dir, [], "{}", "", debug_info, "", "", "", "")
        }

NODE_CLASS_MAPPINGS = {
    "VideoSceneCaption": VideoSceneCaption,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneCaption": "🎬 Video Scene Caption",
}