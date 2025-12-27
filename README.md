ComfyUI-Scene

This ComfyUI extension provides a complete workflow for analyzing video content, generating scene descriptions, and creating AI image prompts. It consists of three interconnected nodes that work together to transform video content into usable AI art prompts with visual previews.

Key Features:
Video Scene Detection - Automatically detects scene changes in videos

AI-Powered Description Generation - Uses Moondream2 vision model to generate detailed scene descriptions

Visual Prompt Selection - Interactive UI to browse and select scenes with image previews

Prompt Customization - Modify image style and lighting parameters

Time-Range Support - Process specific sections of long videos

Real-time Preview - See keyframes and prompts without re-executing nodes

Workflow:
VideoSceneGenerationNode - Analyze video → Detect scenes → Extract keyframes → Generate prompts

ScenePromptSelector - Browse scenes visually → Select prompts → Preview keyframes

ScenePromptModifier - Customize prompts → Adjust style/lighting → Refine for AI generation

📄 Requirements
Python Dependencies:
txt
torch>=2.0.0
torchvision>=0.15.0
transformers>=4.35.0
opencv-python>=4.8.0
Pillow>=10.0.0
scenedetect>=0.6.2
numpy>=1.24.0
aiohttp>=3.9.0
System Requirements:
ComfyUI version with web API support

GPU with CUDA support recommended (for Moondream2 model)

RAM: Minimum 8GB, 16GB+ recommended for video processing

Disk Space: Enough for storing extracted keyframes (typically 100-500MB per video)

Installation:
Clone/copy this folder to ComfyUI/custom_nodes/

Ensure all Python dependencies are installed:

bash
pip install torch torchvision transformers opencv-python Pillow scenedetect numpy aiohttp
Restart ComfyUI

Model Requirements:
Moondream2 (~1.5GB) will be automatically downloaded on first use

Model location: ~/.cache/huggingface/hub/models--vikhyatk--moondream2/

File Structure:
text
video_scene_generation/
├── __init__.py              # Node registration
├── VideoSceneGeneration.py  # Main video analysis node
├── ScenePromptSelector.py   # Scene selection node
├── ScenePromptSelector.js   # Web UI extension
├── ScenePromptRoutes.py     # API endpoints
└── ScenePromptModifier.py   # Prompt editing node
Supported Video Formats:
.mp4, .avi, .mov, .mkv, .webm, .flv, .wmv, .m4v, .mpg, .mpeg

Output Format:
text
output_folder/
├── keyframes/
│   ├── scene_001_01m23s456ms.png
│   ├── scene_001_01m23s456ms.txt
│   ├── scene_002_02m45s789ms.png
│   └── scene_002_02m45s789ms.txt
└── scene_prompts.txt
Notes:
First run will download Moondream2 model (~1-5 minutes depending on internet)

Large videos may require significant disk space for keyframe extraction

Scene detection threshold can be adjusted for different video types

Web UI requires ComfyUI with web server enabled

Troubleshooting:
If scene detection fails, adjust scene_threshold parameter (higher = fewer scenes)

If Moondream2 fails to load, check internet connection and disk space

If images don't preview, ensure ComfyUI web server is running

For long videos, process in time segments using start/end time parameters

<img width="1418" height="895" alt="image" src="https://github.com/user-attachments/assets/251e63d6-c146-4be0-b0c8-f3e008dbc3d6" />

<img width="1426" height="889" alt="image" src="https://github.com/user-attachments/assets/68c97919-833e-43d8-985a-e814c9c6c6b2" />

See workflow in workflow directory

Prompt can be modified before execution in Scene Prompt Selector

Scene Prompt Modifier can modify the prompt without regenerating all scenes.
