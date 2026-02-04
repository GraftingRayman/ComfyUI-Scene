# VideoSceneTranscript.py - Extract spoken words from video scenes
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
import warnings
import subprocess
import shutil
import tempfile
from typing import List, Union
import warnings
warnings.filterwarnings("ignore")

try:
    import comfy.utils
    USE_COMFY_PROGRESS = True
except ImportError:
    USE_COMFY_PROGRESS = False
    print("Note: comfy.utils not available, using simple progress display")

class VideoSceneTranscript:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "scene_video_paths": ("LIST", {
                    "default": [],
                }),
                "speech_model": ([
                    "whisper-large-v3",
                    "whisper-medium",
                    "whisper-small",
                    "whisper-tiny",
                    "none"
                ], {
                    "default": "whisper-medium"
                }),
                "language": ("STRING", {
                    "default": "en",
                    "multiline": False,
                    "placeholder": "Language code (en, zh, fr, de, etc.)"
                }),
                "transcription_mode": ([
                    "transcribe",
                    "translate"
                ], {
                    "default": "transcribe"
                }),
                "timestamps": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Include Timestamps",
                    "label_off": "No Timestamps"
                }),
                "max_transcript_length": ("INT", {
                    "default": 10000,
                    "min": 500,
                    "max": 50000,
                    "step": 100,
                }),
                "use_cache": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Use Cache",
                    "label_off": "Force Regenerate"
                }),
                "keep_model_loaded": ("BOOLEAN", {
                    "default": True,
                    "label_on": "Keep Model",
                    "label_off": "Unload After Use"
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

    RETURN_TYPES = ("STRING", "LIST", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("output_path", "scene_transcripts", "metadata_json", "selected_transcript", "debug_info", "selected_scene_audio")
    FUNCTION = "extract_transcripts"
    CATEGORY = "Video Processing"
    OUTPUT_NODE = True

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.progress_bar = None
        self.whisper_model = None
        self.whisper_processor = None
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
        debug_dir = os.path.join(base_dir, "transcript_debug_logs")
        os.makedirs(debug_dir, exist_ok=True)
        self.debug_dir = debug_dir
        print(f"Transcript debug logs will be saved to: {debug_dir}")
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
            # Check if ffmpeg is available
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode != 0:
                print("FFmpeg not found, cannot extract audio")
                return None
            
            # Use ffmpeg to extract audio to WAV format (better for Whisper)
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # WAV codec
                '-ar', '16000',  # 16kHz sample rate (optimal for Whisper)
                '-ac', '1',  # Mono audio
                '-y',  # Overwrite output
                output_audio_path
            ]
            
            print(f"Extracting audio from: {os.path.basename(video_path)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_audio_path):
                file_size = os.path.getsize(output_audio_path)
                print(f"✓ Audio extracted: {os.path.basename(output_audio_path)} ({file_size/1024/1024:.2f} MB)")
                return output_audio_path
            else:
                print(f"✗ Failed to extract audio: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None
    
    def load_whisper_model(self, model_name):
        """Load Whisper model for speech recognition"""
        if model_name == "none":
            return None, None
        
        if self.whisper_model is not None:
            print(f"Whisper model already loaded, reusing...")
            return self.whisper_processor, self.whisper_model
        
        try:
            print(f"\nLoading Whisper model: {model_name}...\n")
            
            # Try to import transformers
            try:
                from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
                USE_TRANSFORMERS = True
            except ImportError:
                print("transformers not available, trying openai-whisper...")
                USE_TRANSFORMERS = False
            
            if USE_TRANSFORMERS:
                # Use transformers implementation (more memory efficient)
                import torch
                
                model_map = {
                    "whisper-tiny": "openai/whisper-tiny",
                    "whisper-small": "openai/whisper-small",
                    "whisper-medium": "openai/whisper-medium",
                    "whisper-large-v3": "openai/whisper-large-v3",
                }
                
                model_id = model_map.get(model_name, "openai/whisper-medium")
                
                # Load processor
                self.whisper_processor = AutoProcessor.from_pretrained(model_id)
                
                # Load model
                self.whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    low_cpu_mem_usage=True,
                    use_safetensors=True
                ).to(self.device)
                
                self.whisper_model.eval()
                print(f"✓ Whisper model {model_name} loaded successfully via transformers!")
                
            else:
                # Fallback to openai-whisper
                try:
                    import whisper
                    
                    model_map = {
                        "whisper-tiny": "tiny",
                        "whisper-small": "small",
                        "whisper-medium": "medium",
                        "whisper-large-v3": "large-v3",
                    }
                    
                    model_size = model_map.get(model_name, "medium")
                    self.whisper_model = whisper.load_model(model_size, device=self.device)
                    self.whisper_processor = None  # Not needed for openai-whisper
                    
                    print(f"✓ Whisper model {model_name} loaded successfully via openai-whisper!")
                    
                except ImportError:
                    print("Error: Neither transformers nor openai-whisper are available.")
                    print("Please install one of these packages:")
                    print("  pip install transformers accelerate")
                    print("  or")
                    print("  pip install openai-whisper")
                    return None, None
            
            return self.whisper_processor, self.whisper_model
            
        except Exception as e:
            print(f"Failed to load Whisper model: {e}")
            print("\nNote: Whisper models may require additional dependencies.")
            return None, None
    
    def transcribe_audio_whisper(self, audio_path, language="en", task="transcribe", 
                                include_timestamps=True, processor=None, model=None):
        """Transcribe audio using Whisper model"""
        start_time = time.time()
        
        try:
            # Check if audio file exists
            if not os.path.exists(audio_path):
                print(f"  ✗ Audio file not found: {audio_path}")
                return ""
            
            file_size = os.path.getsize(audio_path)
            if file_size < 1000:  # Less than 1KB
                print(f"  ⚠️  Audio file too small: {file_size} bytes")
                return ""
            
            print(f"  Transcribing audio ({file_size/1024/1024:.2f} MB)...")
            
            # Determine if using transformers or openai-whisper
            using_transformers = processor is not None and model is not None
            
            if using_transformers:
                # Using transformers implementation
                import torch
                from transformers import pipeline
                
                # Create pipeline
                pipe = pipeline(
                    "automatic-speech-recognition",
                    model=model,
                    tokenizer=processor.tokenizer,
                    feature_extractor=processor.feature_extractor,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device=self.device,
                )
                
                # Generate transcription
                result = pipe(
                    audio_path,
                    generate_kwargs={
                        "language": language,
                        "task": task,
                    },
                    return_timestamps=include_timestamps,
                )
                
                if include_timestamps:
                    # Format with timestamps
                    transcript = ""
                    for segment in result.get("chunks", []):
                        start = segment.get("timestamp", [0, 0])[0]
                        text = segment.get("text", "").strip()
                        if text:
                            transcript += f"[{start:.2f}s] {text}\n"
                else:
                    transcript = result.get("text", "").strip()
                
            else:
                # Using openai-whisper implementation
                import whisper
                
                # Load audio
                audio = whisper.load_audio(audio_path)
                audio = whisper.pad_or_trim(audio)
                
                # Make log-Mel spectrogram
                mel = whisper.log_mel_spectrogram(audio).to(self.device)
                
                # Detect language if not specified
                if language == "auto":
                    _, probs = model.detect_language(mel)
                    language = max(probs, key=probs.get)
                    print(f"  Detected language: {language}")
                
                # Decode options
                options = whisper.DecodingOptions(
                    language=language,
                    task=task,
                    fp16=torch.cuda.is_available(),
                    without_timestamps=not include_timestamps,
                )
                
                # Transcribe
                result = whisper.decode(model, mel, options)
                
                if include_timestamps:
                    # Get detailed transcription with timestamps
                    result_detail = model.transcribe(
                        audio_path,
                        language=language,
                        task=task,
                        verbose=False,
                    )
                    
                    transcript = ""
                    for segment in result_detail.get("segments", []):
                        start = segment.get("start", 0)
                        text = segment.get("text", "").strip()
                        if text:
                            transcript += f"[{start:.2f}s] {text}\n"
                else:
                    transcript = result.text.strip()
            
            end_time = time.time()
            transcription_time = end_time - start_time
            
            print(f"  ✓ Transcription complete ({len(transcript)} chars, {transcription_time:.2f}s)")
            
            # Save transcription for debugging
            if self.debug_dir:
                self.save_debug_info(
                    "transcription_result.txt",
                    {
                        "audio_file": audio_path,
                        "file_size": file_size,
                        "language": language,
                        "task": task,
                        "include_timestamps": include_timestamps,
                        "transcription_time": transcription_time,
                        "transcript_length": len(transcript),
                        "transcript_preview": transcript[:500] + "..." if len(transcript) > 500 else transcript
                    },
                    step="transcription"
                )
            
            return transcript
            
        except Exception as e:
            end_time = time.time()
            transcription_time = end_time - start_time
            print(f"  ✗ Transcription failed after {transcription_time:.2f}s: {e}")
            
            if self.debug_dir:
                self.save_debug_info(
                    "transcription_error.txt",
                    {
                        "error": str(e),
                        "transcription_time": transcription_time,
                        "audio_file": audio_path,
                        "language": language,
                        "task": task
                    },
                    step="transcription_error"
                )
            
            return ""
    
    def extract_transcripts(self, scene_video_paths, speech_model, language,
                          transcription_mode, timestamps, max_transcript_length,
                          selected_scene_index, use_cache, keep_model_loaded,
                          video_scenes_output_path=""):
        
        print(f"\n{'='*60}")
        print(f"🎤 VideoSceneTranscript: Starting transcript extraction")
        print(f"Selected scene index: {selected_scene_index}")
        print(f"Speech model: {speech_model}")
        print(f"Language: {language}")
        print(f"Mode: {transcription_mode}")
        print(f"Timestamps: {'Enabled' if timestamps else 'Disabled'}")
        print(f"Use cache: {use_cache}")
        print(f"Keep model loaded: {keep_model_loaded}")
        print(f"{'='*60}")
        
        debug_info_lines = []
        debug_info_lines.append(f"VideoSceneTranscript Debug Information")
        debug_info_lines.append(f"{'='*60}")
        debug_info_lines.append(f"Selected scene index: {selected_scene_index}")
        debug_info_lines.append(f"Speech model: {speech_model}")
        debug_info_lines.append(f"Language: {language}")
        debug_info_lines.append(f"Mode: {transcription_mode}")
        debug_info_lines.append(f"Timestamps: {'Enabled' if timestamps else 'Disabled'}")
        debug_info_lines.append(f"Use cache: {use_cache}")
        debug_info_lines.append(f"Keep model loaded: {keep_model_loaded}")
        debug_info_lines.append(f"Total input video paths: {len(scene_video_paths) if scene_video_paths else 0}")
        
        # Determine output directory
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
        
        # Setup debug logging
        debug_dir = self.setup_debug_logging(base_dir)
        
        # Create transcripts subdirectory
        transcripts_dir = os.path.join(base_dir, "scene_transcripts")
        os.makedirs(transcripts_dir, exist_ok=True)
        debug_info_lines.append(f"Transcripts directory: {transcripts_dir}")
        debug_info_lines.append(f"Base directory: {base_dir}")
        
        # Create audio cache directory
        audio_cache_dir = os.path.join(base_dir, "audio_cache")
        os.makedirs(audio_cache_dir, exist_ok=True)
        debug_info_lines.append(f"Audio cache directory: {audio_cache_dir}")
        
        # Initialize selected scene audio path
        selected_scene_audio_path = ""
        
        # Get video files
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
            return self.return_empty(transcripts_dir, selected_scene_index)
        
        debug_info_lines.append(f"Found {len(valid_video_paths)} valid video files")
        
        # Generate cache key
        cache_key_params = f"{len(valid_video_paths)}_{speech_model}_{language}_{transcription_mode}_{timestamps}_{base_dir}"
        cache_key = hashlib.md5(cache_key_params.encode()).hexdigest()[:16]
        
        cache_file = os.path.join(transcripts_dir, f"cache_{cache_key}.json")
        
        scene_transcripts = []
        metadata = {
            "base_directory": base_dir,
            "transcripts_directory": transcripts_dir,
            "speech_model": speech_model,
            "language": language,
            "transcription_mode": transcription_mode,
            "include_timestamps": timestamps,
            "max_transcript_length": max_transcript_length,
            "use_cache": use_cache,
            "keep_model_loaded": keep_model_loaded,
            "total_scenes": len(valid_video_paths),
            "scenes": []
        }
        
        video_paths_changed = self.last_video_paths != valid_video_paths
        cache_valid = False
        
        if use_cache and os.path.exists(cache_file) and not video_paths_changed:
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                scene_transcripts = cached_data.get("scene_transcripts", [])
                metadata = cached_data.get("metadata", metadata)
                
                if len(scene_transcripts) == len(valid_video_paths):
                    cache_valid = True
                    print(f"\n✓ CACHE HIT: Loaded {len(scene_transcripts)} cached transcripts")
                    print(f"  Cache file: {cache_file}")
                    print(f"  Skipping transcription processing...\n")
                    debug_info_lines.append(f"✓ Loaded {len(scene_transcripts)} cached transcripts")
                else:
                    debug_info_lines.append(f"Cache invalid: expected {len(valid_video_paths)} transcripts, got {len(scene_transcripts)}")
                    scene_transcripts = []
            except Exception as e:
                debug_info_lines.append(f"Error loading cache: {e}")
        
        self.last_video_paths = valid_video_paths
        self.last_index = selected_scene_index
        
        if not cache_valid:
            print(f"\n{'='*60}")
            print(f"🔄 CACHE MISS: Processing {len(valid_video_paths)} videos...")
            print(f"{'='*60}\n")
            
            # Load Whisper model
            debug_info_lines.append(f"\nLoading Whisper model: {speech_model}...")
            processor, model = self.load_whisper_model(speech_model)
            if not model:
                debug_info_lines.append(f"Failed to load Whisper model")
                print("Failed to load Whisper model")
                return self.return_empty(transcripts_dir, selected_scene_index)
            
            scene_transcripts = []
            metadata["scenes"] = []
            
            total_videos = len(valid_video_paths)
            self.create_progress_bar(total_videos, "Extracting transcripts")
            
            for i, video_path in enumerate(valid_video_paths):
                scene_number = i + 1  # 1-based scene number
                video_filename = os.path.basename(video_path)
                
                print(f"\n{'─'*60}")
                print(f"🎤 Processing Scene {scene_number}/{total_videos}: {video_filename}")
                print(f"{'─'*60}")
                
                debug_info_lines.append(f"\nProcessing scene {scene_number}/{total_videos}: {video_filename}")
                
                self.update_progress(i + 1, total_videos, f"Scene {scene_number}/{total_videos}")
                
                # Get video info
                duration = self.get_video_duration(video_path)
                print(f"  Duration: {duration:.2f}s")
                debug_info_lines.append(f"  Duration: {duration:.2f}s")
                
                # Extract audio if needed
                audio_cache_path = os.path.join(audio_cache_dir, f"scene_{scene_number:04d}_audio.wav")
                
                if not os.path.exists(audio_cache_path):
                    print(f"  Extracting audio...")
                    audio_path = self.extract_audio_from_video(video_path, audio_cache_path)
                    if not audio_path:
                        print(f"  ✗ Failed to extract audio")
                        debug_info_lines.append(f"  ✗ Failed to extract audio")
                        scene_transcripts.append("")
                        continue
                else:
                    print(f"  ✓ Using cached audio")
                    audio_path = audio_cache_path
                    debug_info_lines.append(f"  Using cached audio")
                
                # If this is the selected scene, store the audio path
                is_selected_scene = (scene_number == selected_scene_index)
                if is_selected_scene:
                    selected_scene_audio_path = audio_path
                    print(f"  ✓ This is selected scene, storing audio path")
                
                # Transcribe audio
                task = transcription_mode
                if language.lower() == "auto":
                    lang = None
                else:
                    lang = language
                
                transcript = self.transcribe_audio_whisper(
                    audio_path=audio_path,
                    language=lang,
                    task=task,
                    include_timestamps=timestamps,
                    processor=processor,
                    model=model
                )
                
                # Clean and limit transcript length
                if transcript:
                    transcript = transcript.strip()
                    if len(transcript) > max_transcript_length:
                        transcript = transcript[:max_transcript_length].rsplit(' ', 1)[0] + "..."
                else:
                    transcript = "No speech detected."
                
                scene_transcripts.append(transcript)
                
                # Save individual transcript files
                transcript_filename = f"scene_{scene_number:04d}_transcript.txt"
                transcript_filepath = os.path.join(transcripts_dir, transcript_filename)
                with open(transcript_filepath, 'w', encoding='utf-8') as f:
                    f.write(transcript + '\n')
                
                print(f"  ✓ Transcript saved: {transcript_filename}")
                print(f"  Transcript length: {len(transcript)} characters")
                debug_info_lines.append(f"  ✓ Transcript saved ({len(transcript)} chars)")
                
                # Add to metadata
                scene_metadata = {
                    "index": i,
                    "scene_number": scene_number,
                    "video_path": video_path,
                    "video_filename": video_filename,
                    "audio_path": audio_path,
                    "duration": duration,
                    "transcript": transcript,
                    "transcript_file": transcript_filename,
                    "transcript_filepath": transcript_filepath,
                    "is_selected_scene": is_selected_scene,
                    "has_speech": transcript != "No speech detected." and len(transcript) > 0,
                    "transcript_length": len(transcript)
                }
                
                metadata["scenes"].append(scene_metadata)
            
            # Cache results
            if use_cache:
                cache_data = {
                    "scene_transcripts": scene_transcripts,
                    "metadata": metadata,
                    "cache_key": cache_key
                }
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                print(f"\n✓ Results cached: {cache_file}")
                debug_info_lines.append(f"\n✓ Results cached: {cache_file}")
            
            # Clean up model based on user preference
            if keep_model_loaded:
                print("\n✓ Keeping Whisper model loaded for future use...")
                debug_info_lines.append("\nKeeping Whisper model loaded for future use...")
            else:
                print("\n🗑️ Unloading Whisper model...")
                debug_info_lines.append("\nUnloading Whisper model...")
                if self.whisper_model:
                    del self.whisper_model
                    self.whisper_model = None
                    self.whisper_processor = None
                
                torch.cuda.empty_cache()
                print("✓ Model unloaded and GPU memory cleared")
                debug_info_lines.append("Model unloaded and GPU memory cleared")
        
        else:
            # Cache is valid - load from cache
            debug_info_lines.append(f"\n{'='*60}")
            debug_info_lines.append(f"✓ Using cached transcripts - skipping transcription processing")
            debug_info_lines.append(f"  Cached scenes: {len(scene_transcripts)}")
            debug_info_lines.append(f"  Cache file: {cache_file}")
            debug_info_lines.append(f"{'='*60}")
            
            # Still need to get audio path for selected scene
            internal_index = selected_scene_index - 1
            if 0 <= internal_index < len(valid_video_paths):
                video_path = valid_video_paths[internal_index]
                audio_cache_path = os.path.join(audio_cache_dir, f"scene_{selected_scene_index:04d}_audio.wav")
                
                if os.path.exists(audio_cache_path):
                    selected_scene_audio_path = audio_cache_path
                    print(f"✓ Found cached audio for selected scene: {os.path.basename(audio_cache_path)}")
                else:
                    # Extract audio if not cached
                    print(f"\n📦 Extracting audio for selected scene {selected_scene_index}...")
                    audio_path = self.extract_audio_from_video(video_path, audio_cache_path)
                    if audio_path:
                        selected_scene_audio_path = audio_path
                        print(f"  ✓ Audio extracted: {os.path.basename(audio_path)}")
                    else:
                        print(f"  ✗ Failed to extract audio")
        
        # Save metadata
        metadata_path = os.path.join(transcripts_dir, "transcripts_metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        debug_info_lines.append(f"\nMetadata saved: {metadata_path}")
        
        # Get selected transcript
        internal_index = selected_scene_index - 1
        selected_transcript = ""
        
        if 0 <= internal_index < len(scene_transcripts):
            selected_transcript = scene_transcripts[internal_index]
            debug_info_lines.append(f"\nSelected transcript (scene {selected_scene_index}):")
            debug_info_lines.append(f"  {selected_transcript[:200]}..." if len(selected_transcript) > 200 else f"  {selected_transcript}")
        elif scene_transcripts:
            selected_transcript = scene_transcripts[0]
            internal_index = 0
            debug_info_lines.append(f"\nSelected index out of bounds, using first transcript")
        
        # Add final summary to debug info
        debug_info_lines.append(f"\n{'='*60}")
        debug_info_lines.append(f"✓ Complete! Extracted {len(scene_transcripts)} scene transcripts")
        debug_info_lines.append(f"  Output directory: {transcripts_dir}")
        debug_info_lines.append(f"  Selected scene: {selected_scene_index} (internal: {internal_index})")
        debug_info_lines.append(f"  Selected transcript length: {len(selected_transcript)} characters")
        
        # Calculate speech statistics
        if scene_transcripts:
            speech_scenes = sum(1 for t in scene_transcripts if t and t != "No speech detected." and len(t.strip()) > 10)
            total_chars = sum(len(t) for t in scene_transcripts)
            avg_chars = total_chars // len(scene_transcripts) if scene_transcripts else 0
            
            debug_info_lines.append(f"\nSpeech Statistics:")
            debug_info_lines.append(f"  Scenes with speech: {speech_scenes}/{len(scene_transcripts)}")
            debug_info_lines.append(f"  Total characters: {total_chars}")
            debug_info_lines.append(f"  Average per scene: {avg_chars} characters")
        
        # Compile final debug info
        debug_info = "\n".join(debug_info_lines)
        
        # Print summary to console
        print(f"\n{'='*60}")
        print(f"✓ Complete! Extracted {len(scene_transcripts)} scene transcripts")
        print(f"  Base directory: {base_dir}")
        print(f"  Transcripts directory: {transcripts_dir}")
        print(f"  Selected scene: {selected_scene_index}")
        print(f"  Speech model: {speech_model}")
        print(f"  Language: {language}")
        print(f"  Mode: {transcription_mode}")
        print(f"  Timestamps: {'Enabled' if timestamps else 'Disabled'}")
        print(f"  Use cache: {use_cache}")
        print(f"  Keep model loaded: {keep_model_loaded}")
        print(f"{'='*60}")
        
        # Return results
        return {
            "ui": {
                "text": [selected_transcript],
                "scene_transcripts": [scene_transcripts],
                "total_scenes": [len(scene_transcripts)],
                "selected_index": [selected_scene_index],
                "transcripts_dir": [transcripts_dir],
                "base_dir": [base_dir],
                "debug_info": [debug_info],
                "selected_scene_audio": [selected_scene_audio_path],
            },
            "result": (
                transcripts_dir, 
                scene_transcripts, 
                json.dumps(metadata, indent=2), 
                selected_transcript,
                debug_info,
                selected_scene_audio_path
            )
        }
    
    def return_empty(self, output_dir, selected_scene_index):
        """Return empty results"""
        debug_info = f"No video files found to process.\nOutput directory: {output_dir}\nSelected scene index: {selected_scene_index}"
        
        return {
            "ui": {
                "text": [""],
                "scene_transcripts": [[]],
                "total_scenes": [0],
                "selected_index": [selected_scene_index],
                "transcripts_dir": [output_dir],
                "base_dir": [output_dir],
                "debug_info": [debug_info],
                "selected_scene_audio": [""],
            },
            "result": (output_dir, [], "{}", "", debug_info, "")
        }
    
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

# Register the node
NODE_CLASS_MAPPINGS = {
    "VideoSceneTranscript": VideoSceneTranscript,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoSceneTranscript": "🎤 Video Scene Transcript",
}